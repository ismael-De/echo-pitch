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
#   ./infra/deploy_aca.sh
set -euo pipefail

RG=${AZ_RG:-echo-pitch-rg}
LOC=${AZ_LOCATION:-swedencentral}
ACR=${AZ_ACR:?set AZ_ACR to a globally unique registry name (lowercase letters/digits)}
ENV_NAME=${AZ_ENV:-echo-pitch-env}
APP=${AZ_APP:-echo-pitch}
TAG=${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo latest)}
MODE=${LLM_MODE:-$([ -n "${FOUNDRY_PROJECT_ENDPOINT:-}" ] && echo foundry || echo offline)}

echo "==> Resource group $RG ($LOC)"
az group create -n "$RG" -l "$LOC" -o none

echo "==> Container registry $ACR + cloud build"
az acr create -g "$RG" -n "$ACR" --sku Basic -o none
az acr build -r "$ACR" -t "echo-pitch:$TAG" .

echo "==> Container Apps environment $ENV_NAME"
az containerapp env create -g "$RG" -n "$ENV_NAME" -l "$LOC" -o none

echo "==> Container app $APP (LLM_MODE=$MODE)"
az containerapp create -g "$RG" -n "$APP" --environment "$ENV_NAME" \
  --image "$ACR.azurecr.io/echo-pitch:$TAG" --registry-server "$ACR.azurecr.io" --registry-identity system \
  --system-assigned --ingress external --target-port 8000 \
  --min-replicas 0 --max-replicas 1 --cpu 0.5 --memory 1.0Gi \
  --env-vars LLM_MODE="$MODE" FOUNDRY_PROJECT_ENDPOINT="${FOUNDRY_PROJECT_ENDPOINT:-}" \
             FOUNDRY_MODEL="${FOUNDRY_MODEL:-gpt-5-mini}" LLM_TIMEOUT_S=8 LLM_RETRIES=1 FOUNDRY_CREDENTIAL=managed \
             BUDGET_STREAMS_PER_IP_HOUR=6 BUDGET_STREAMS_PER_DAY=150 BUDGET_MAX_CONCURRENT=4 -o none
# Cheapest: scale to zero when idle (first visit has a cold start) and a single replica, so the in-memory
# replay sessions and the spend guard (app/budget.py) live in one process. SSE needs no special ingress settings.

if [ "$MODE" = "foundry" ] && [ -n "${FOUNDRY_ACCOUNT_ID:-}" ]; then
  echo "==> Grant the app's managed identity access to Foundry (keyless auth via DefaultAzureCredential)"
  PRINCIPAL=$(az containerapp show -g "$RG" -n "$APP" --query identity.principalId -o tsv)
  az role assignment create --assignee-object-id "$PRINCIPAL" --assignee-principal-type ServicePrincipal \
    --role "Azure AI User" --scope "$FOUNDRY_ACCOUNT_ID" -o none
fi

URL=$(az containerapp show -g "$RG" -n "$APP" --query properties.configuration.ingress.fqdn -o tsv)
echo "==> Deployed: https://$URL"
