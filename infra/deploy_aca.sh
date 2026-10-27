#!/usr/bin/env bash
# Deploy Echo Pitch to Azure Container Apps with the az CLI.
# NOT run automatically. Prerequisites: `az login`, an Azure subscription, and (for LLM mode)
# a Microsoft Foundry project with a model deployment.
#
# Usage:
#   export AZ_RG=echo-pitch-rg AZ_LOCATION=swedencentral AZ_ACR=echopitch$RANDOM
#   export FOUNDRY_PROJECT_ENDPOINT=https://<account>.services.ai.azure.com/api/projects/<project>
#   export FOUNDRY_MODEL=gpt-5-mini
#   export FOUNDRY_ACCOUNT_ID=/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>
#   ./infra/deploy_aca.sh            # LOCAL_BUILD=docker|podman if ACR Tasks are blocked
set -euo pipefail

RG=${AZ_RG:-echo-pitch-rg}
LOC=${AZ_LOCATION:-swedencentral}
ACR=${AZ_ACR:?set AZ_ACR to a globally unique registry name (lowercase letters/digits)}
ENV_NAME=${AZ_ENV:-echo-pitch-std}
APP=${AZ_APP:-echo-pitch-web}
UAMI=${AZ_IDENTITY:-echo-pitch-id}
TAG=${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo latest)}
MODE=${LLM_MODE:-$([ -n "${FOUNDRY_PROJECT_ENDPOINT:-}" ] && echo foundry || echo offline)}

echo "==> Resource group $RG ($LOC)"
az group create -n "$RG" -l "$LOC" -o none

echo "==> Container registry $ACR + cloud build"
az acr show -n "$ACR" -o none 2>/dev/null || az acr create -g "$RG" -n "$ACR" --sku Basic -o none
if [ "${LOCAL_BUILD:-}" = "crane" ]; then
  # No docker/podman and no ACR Tasks: append a layer onto the running image (see infra/crane_build.sh)
  az acr login -n "$ACR" --expose-token --query accessToken -o tsv |
    crane auth login "$ACR.azurecr.io" -u 00000000-0000-0000-0000-000000000000 --password-stdin
  BASE_IMAGE=${BASE_IMAGE:-$(az containerapp show -g "$RG" -n "$APP" --query "properties.template.containers[0].image" -o tsv)} \
    NEW_IMAGE="$ACR.azurecr.io/echo-pitch:$TAG" infra/crane_build.sh
elif [ -n "${LOCAL_BUILD:-}" ]; then
  # Some subscriptions (e.g. Azure for Students) block ACR Tasks: build locally with docker/podman and push.
  "$LOCAL_BUILD" build -t "$ACR.azurecr.io/echo-pitch:$TAG" .
  az acr login -n "$ACR" --expose-token --query accessToken -o tsv |
    "$LOCAL_BUILD" login "$ACR.azurecr.io" -u 00000000-0000-0000-0000-000000000000 --password-stdin
  "$LOCAL_BUILD" push "$ACR.azurecr.io/echo-pitch:$TAG"
else
  az acr build -r "$ACR" -t "echo-pitch:$TAG" .
fi

echo "==> Container Apps environment $ENV_NAME"
az containerapp env show -g "$RG" -n "$ENV_NAME" -o none 2>/dev/null || \
  az containerapp env create -g "$RG" -n "$ENV_NAME" -l "$LOC" --logs-destination none -o none

echo "==> User-assigned identity $UAMI (image pull + keyless Foundry access)"
# A user-assigned identity (not system-assigned) is used because some subscriptions (e.g. Azure for Students)
# get "express" Container Apps environments, which reject any later update of an app with a system-assigned
# identity. With a user-assigned identity, `az containerapp update --image ...` works for future releases.
az identity show -g "$RG" -n "$UAMI" -o none 2>/dev/null || az identity create -g "$RG" -n "$UAMI" -l "$LOC" -o none
UAMI_ID=$(az identity show -g "$RG" -n "$UAMI" --query id -o tsv)
UAMI_CLIENT=$(az identity show -g "$RG" -n "$UAMI" --query clientId -o tsv)
UAMI_PRINCIPAL=$(az identity show -g "$RG" -n "$UAMI" --query principalId -o tsv)
az role assignment create --assignee-object-id "$UAMI_PRINCIPAL" --assignee-principal-type ServicePrincipal \
  --role AcrPull --scope "$(az acr show -n "$ACR" --query id -o tsv)" -o none
if [ "$MODE" = "foundry" ] && [ -n "${FOUNDRY_ACCOUNT_ID:-}" ]; then
  az role assignment create --assignee-object-id "$UAMI_PRINCIPAL" --assignee-principal-type ServicePrincipal \
    --role "Cognitive Services User" --scope "$FOUNDRY_ACCOUNT_ID" -o none
fi
sleep 30  # let the role assignments propagate before the first image pull

if az containerapp show -g "$RG" -n "$APP" -o none 2>/dev/null; then
  echo "==> Updating $APP to $TAG"
  if [ -n "${AZURE_SPEECH_KEY:-}" ]; then  # spoken commentary (Azure AI Speech), key kept as an app secret
    az containerapp secret set -g "$RG" -n "$APP" --secrets speech-key="$AZURE_SPEECH_KEY" -o none
    az containerapp update -g "$RG" -n "$APP" --image "$ACR.azurecr.io/echo-pitch:$TAG" \
      --set-env-vars AZURE_SPEECH_KEY=secretref:speech-key AZURE_SPEECH_REGION="${AZURE_SPEECH_REGION:-uaenorth}" -o none
  else
    az containerapp update -g "$RG" -n "$APP" --image "$ACR.azurecr.io/echo-pitch:$TAG" -o none
  fi
else
  echo "==> Container app $APP (LLM_MODE=$MODE)"
  az containerapp create -g "$RG" -n "$APP" --environment "$ENV_NAME" \
    --image "$ACR.azurecr.io/echo-pitch:$TAG" --registry-server "$ACR.azurecr.io" --registry-identity "$UAMI_ID" \
    --user-assigned "$UAMI_ID" --ingress external --target-port 8000 \
    --min-replicas 0 --max-replicas 1 --cpu 0.5 --memory 1.0Gi \
    --env-vars LLM_MODE="$MODE" FOUNDRY_PROJECT_ENDPOINT="${FOUNDRY_PROJECT_ENDPOINT:-}" \
               FOUNDRY_MODEL="${FOUNDRY_MODEL:-gpt-5-mini}" LLM_TIMEOUT_S=8 LLM_RETRIES=1 \
               FOUNDRY_CREDENTIAL=managed AZURE_CLIENT_ID="$UAMI_CLIENT" \
               BUDGET_STREAMS_PER_IP_HOUR=6 BUDGET_STREAMS_PER_DAY=150 BUDGET_MAX_CONCURRENT=4 -o none
fi
# Cheapest: scale to zero when idle (first visit has a cold start) and a single replica, so the in-memory
# replay sessions and the spend guard (app/budget.py) live in one process. SSE needs no special ingress settings.

URL=$(az containerapp show -g "$RG" -n "$APP" --query properties.configuration.ingress.fqdn -o tsv)
echo "==> Deployed: https://$URL"
