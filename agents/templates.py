"""Deterministic EN/AR templates used offline and as the fallback when an LLM call fails.

Variants are picked by a stable hash of the event id so output is reproducible.
Names of fictional clubs/players stay in Latin script inside Arabic sentences.
"""
from __future__ import annotations

import zlib

LINES = {
    "en": {
        "goal": {
            "fan": ["GOAL! {player} scores for {team}! {score}",
                    "It's in! {player} sends the {team} fans wild! {score}",
                    "{player} finds the net! What a moment for {team}! {score}"],
            "analyst": ["Goal: {player} ({team}) converts a {xg} xG chance from {dist}m. {score}",
                        "{player} scores from {dist}m (xG {xg}), shot speed {speed} km/h. {score}"]},
        "shot_saved": {
            "fan": ["{player} tries his luck, but the keeper says no!", "Good effort from {player}, held by the keeper."],
            "analyst": ["{player} forces a save from {dist}m (xG {xg}).", "On target from {player}: {xg} xG, {speed} km/h, saved."]},
        "shot_off_target": {
            "fan": ["{player} lets fly... and it's wide.", "Over the bar from {player}!"],
            "analyst": ["{player} misses the target from {dist}m (xG {xg}).", "Off target: {player}, {xg} xG under pressure {press}."]},
        "shot_blocked": {
            "fan": ["{player} shoots, but it's blocked!", "Bodies on the line to stop {player}!"],
            "analyst": ["{player}'s {xg} xG effort is blocked.", "Blocked shot from {player} ({dist}m)."]},
        "save_wonder": {
            "fan": ["WHAT A SAVE from {player}! Unbelievable!", "{player} flies across goal to keep it out! Incredible!"],
            "analyst": ["Elite save: {player} stops a {xg} xG shot.", "{player} prevents {xg} xG with a reflex stop."]},
        "save": {
            "fan": ["Safe hands from {player}.", "{player} gathers comfortably."],
            "analyst": ["{player} saves ({xg} xG faced).", "Routine stop for {player}, {xg} xG."]},
        "tackle": {
            "fan": ["Great tackle by {player}!", "{player} wins it back for {team}!"],
            "analyst": ["{player} wins the ball at {zone}.", "Ball regained by {player} ({zone})."]},
        "foul": {
            "fan": ["Foul by {player}, free kick.", "{player} goes in late, the referee blows."],
            "analyst": ["Foul by {player} in the {zone}; {team} fouls: {fouls}.", "{player} stops the move illegally ({zone})."]},
        "hard_pass": {
            "fan": ["Lovely ball from {player}!", "{player} threads a beauty through!"],
            "analyst": ["Pass difficulty {diff}/100 completed by {player}, {length}m into the final third.",
                        "{player} breaks the line: {length}m pass, difficulty {diff}."]},
        "speed": {
            "fan": ["{player} is flying down the pitch!", "Look at the pace on {player}!"],
            "analyst": ["{player} carries {length}m at {speed} km/h.", "Speed alert: {player} at {speed} km/h."]},
        "insight": {"fan": ["{dom} are on top right now with {pos}% of the ball."],
                    "analyst": ["Stats check {clock}: possession {pos_h}%-{pos_a}%, xG {xg_h}-{xg_a}, shots {sh_h}-{sh_a}. Phase: {phase}."]},
        "kickoff": {"fan": ["We're under way: {home} against {away}!"],
                    "analyst": ["Kick-off: {home} v {away}, both in 4-3-3."]},
        "halftime": {"fan": ["Half-time: {score}."], "analyst": ["Half-time: {score}. xG {xg_h}-{xg_a}, possession {pos_h}%-{pos_a}%."]},
        "fulltime": {"fan": ["Full-time! {score}."], "analyst": ["Full-time: {score}. xG {xg_h}-{xg_a}."]},
    },
    "ar": {
        "goal": {
            "fan": ["هدف! {player} يسجّل لـ{team}! {score}",
                    "الكرة في الشباك! {player} يُشعل مدرجات {team}! {score}",
                    "يا لها من لحظة! {player} يهزّ الشباك لـ{team}! {score}"],
            "analyst": ["هدف: {player} ({team}) يحوّل فرصة قيمتها {xg} xG من {dist} متر. {score}",
                        "{player} يسجّل من {dist} متر (xG {xg})، وسرعة التسديدة {speed} كم/س. {score}"]},
        "shot_saved": {
            "fan": ["{player} يجرّب حظّه، لكن الحارس يتصدّى!", "محاولة جيدة من {player}، والحارس يمسك الكرة."],
            "analyst": ["{player} يجبر الحارس على التصدي من {dist} متر (xG {xg}).", "تسديدة على المرمى من {player}: {xg} xG بسرعة {speed} كم/س، وتم التصدي لها."]},
        "shot_off_target": {
            "fan": ["{player} يسدد... والكرة بجانب القائم.", "تسديدة {player} تعلو العارضة!"],
            "analyst": ["{player} يخطئ المرمى من {dist} متر (xG {xg}).", "خارج المرمى: {player}، {xg} xG تحت ضغط {press}."]},
        "shot_blocked": {
            "fan": ["{player} يسدد، لكن الدفاع يصدّها!", "الدفاع يرمي بنفسه أمام تسديدة {player}!"],
            "analyst": ["صدّ الدفاع محاولة {player} ({xg} xG).", "تسديدة مصدودة من {player} من {dist} متر."]},
        "save_wonder": {
            "fan": ["يا له من تصدٍّ رائع من {player}! لا يُصدَّق!", "{player} يطير ويُبعد الكرة! مذهل!"],
            "analyst": ["تصدٍّ من الطراز الرفيع: {player} يمنع فرصة قيمتها {xg} xG.", "{player} يحرم المنافس من {xg} xG بردّة فعل سريعة."]},
        "save": {
            "fan": ["{player} يمسك الكرة بثقة.", "الحارس {player} في الموعد."],
            "analyst": ["تصدٍّ من {player} (xG {xg}).", "تصدٍّ سهل لـ{player}، {xg} xG."]},
        "tackle": {
            "fan": ["تدخّل رائع من {player}!", "{player} يستعيد الكرة لـ{team}!"],
            "analyst": ["{player} يستخلص الكرة في {zone}.", "استعادة للكرة عبر {player} ({zone})."]},
        "foul": {
            "fan": ["خطأ من {player}، ضربة حرة.", "{player} يتأخر في التدخل، والحكم يصفّر."],
            "analyst": ["خطأ من {player} في {zone}؛ أخطاء {team}: {fouls}.", "{player} يوقف الهجمة بخطأ ({zone})."]},
        "hard_pass": {
            "fan": ["كرة رائعة من {player}!", "{player} يمرّر كرة ساحرة!"],
            "analyst": ["تمريرة بصعوبة {diff}/100 ينجح فيها {player}، {length} متر نحو الثلث الأخير.",
                        "{player} يكسر الخطوط: تمريرة {length} متر بصعوبة {diff}."]},
        "speed": {
            "fan": ["{player} ينطلق كالسهم!", "انظروا إلى سرعة {player}!"],
            "analyst": ["{player} يتقدم بالكرة {length} متر بسرعة {speed} كم/س.", "تنبيه سرعة: {player} بسرعة {speed} كم/س."]},
        "insight": {"fan": ["{dom} هو الأفضل حالياً بنسبة استحواذ {pos}%."],
                    "analyst": ["لغة الأرقام {clock}: الاستحواذ {pos_h}%-{pos_a}%، xG {xg_h}-{xg_a}، التسديدات {sh_h}-{sh_a}. طابع اللعب: {phase}."]},
        "kickoff": {"fan": ["انطلقت المباراة: {home} ضد {away}!"], "analyst": ["البداية: {home} ضد {away}، بخطة 4-3-3 للطرفين."]},
        "halftime": {"fan": ["نهاية الشوط الأول: {score}."], "analyst": ["نهاية الشوط الأول: {score}. xG {xg_h}-{xg_a}، الاستحواذ {pos_h}%-{pos_a}%."]},
        "fulltime": {"fan": ["نهاية المباراة! {score}."], "analyst": ["نهاية المباراة: {score}. xG {xg_h}-{xg_a}."]},
    },
}

ZONES = {"en": ("defensive third", "midfield", "final third"), "ar": ("الثلث الدفاعي", "وسط الملعب", "الثلث الأخير")}

FAVOURITE = {
    "en": {"for": ["Come on, {club}!", "Yes, {club}!"], "against": ["Uh-oh for {club}...", "Danger for {club}!"],
           "star": "★ {player}"},
    "ar": {"for": ["هيا يا {club}!", "رائع يا {club}!"], "against": ["خطر على {club}...", "انتبه يا {club}!"],
           "star": "★ {player}"},
}

MOMENTS = {
    "en": {
        "goal_lead": "{team} take the lead. It changes the game state: {opp} now have to open up.",
        "goal_equaliser": "An equaliser. {team} wipe out the deficit and the match is level again.",
        "goal_extend": "{team} double down: a two-goal cushion makes a comeback much harder.",
        "goal_extend_more": "{team} extend the lead to {margin}; this looks decisive.",
        "goal_pullback": "{team} pull one back; game on, they're within {margin}.",
        "late": " Coming in minute {minute}, there is little time to respond.",
        "against_run": " It came against the run of play: {opp} had the momentum.",
        "with_run": " It capped a spell of sustained {team} pressure.",
        "low_xg": " A low-probability finish ({xg} xG): only about {pct} in 100 such chances go in.",
        "high_xg": " A high-quality chance ({xg} xG) that {team} had worked for.",
        "big_chance": "{player} should have scored: a {xg} xG chance is converted roughly {pct} times in 100. A huge let-off for {opp}.",
        "key_save": "{player} kept out a {xg} xG chance, worth roughly {pct}% of a goal to {opp}.",
        "wonder": " A world-class reflex save that protects the scoreline.",
        "pressure_spike": "{team} turned up the press ({value} vs a match average of {avg}). This period had {turnovers} turnovers and the game felt {phase}.",
        "titles": {"goal": "GOAL", "big_chance_missed": "BIG CHANCE", "key_save": "KEY SAVE", "pressure_spike": "PRESSING SURGE"},
        "phase": {"controlled": "controlled", "contested": "contested", "chaotic": "chaotic"},
    },
    "ar": {
        "goal_lead": "{team} يتقدم في النتيجة، وهذا يغيّر مجرى اللقاء: على {opp} الآن أن يهاجم.",
        "goal_equaliser": "هدف التعادل! {team} يمحو التأخر وتعود المباراة إلى نقطة البداية.",
        "goal_extend": "{team} يضاعف تقدمه، وفارق الهدفين يجعل العودة أصعب بكثير.",
        "goal_extend_more": "{team} يوسّع الفارق إلى {margin}، ويبدو أن الأمر قد حُسم.",
        "goal_pullback": "{team} يقلّص الفارق إلى {margin}، والمباراة لم تنتهِ بعد.",
        "late": " جاء في الدقيقة {minute}، ولم يتبقَّ وقت كبير للرد.",
        "against_run": " جاء عكس مجرى اللعب، فقد كانت الأفضلية لـ{opp}.",
        "with_run": " جاء تتويجاً لفترة ضغط متواصل من {team}.",
        "low_xg": " إنهاء صعب ({xg} xG): نحو {pct} فقط من كل 100 فرصة مشابهة تدخل المرمى.",
        "high_xg": " فرصة عالية الجودة ({xg} xG) صنعها {team} بجدارة.",
        "big_chance": "كان على {player} أن يسجّل: فرصة بقيمة {xg} xG تُترجم نحو {pct} مرة من كل 100. نجاة كبيرة لـ{opp}.",
        "key_save": "{player} أبعد فرصة بقيمة {xg} xG، أي ما يعادل نحو {pct}% من هدف لـ{opp}.",
        "wonder": " تصدٍّ عالمي بردّة فعل خاطفة يحمي النتيجة.",
        "pressure_spike": "{team} رفع وتيرة الضغط ({value} مقابل متوسط {avg} في المباراة). وتبدّلت الحيازة {turnovers} مرة في هذه الفترة، وكان طابع اللعب {phase}.",
        "titles": {"goal": "هدف", "big_chance_missed": "فرصة ضائعة", "key_save": "تصدٍّ حاسم", "pressure_spike": "موجة ضغط"},
        "phase": {"controlled": "منظّماً", "contested": "متكافئاً", "chaotic": "فوضوياً"},
    },
}

RECAP = {
    "en": {
        "result_win": "{winner} beat {loser} {score} at {venue}.",
        "result_draw": "{home} and {away} drew {score} at {venue}.",
        "xg_fair": " On expected goals ({xg_h}-{xg_a}) the result was a fair reflection.",
        "xg_unfair": " The xG ({xg_h}-{xg_a}) suggests {better} deserved more.",
        "goals": " Goals: {goals}.",
        "no_goals": " Neither side found a way through.",
        "control": " {dom} controlled the ball ({pos}% possession) and completed {comp}% of passes.",
        "save": " Save of the match: {keeper} denying a {xg} xG chance in minute {minute}.",
        "potm": " Player of the match: {player} ({team}).",
    },
    "ar": {
        "result_win": "فاز {winner} على {loser} بنتيجة {score} على ملعب {venue}.",
        "result_draw": "تعادل {home} و{away} بنتيجة {score} على ملعب {venue}.",
        "xg_fair": " وتعكس الأهداف المتوقعة ({xg_h}-{xg_a}) عدالة النتيجة.",
        "xg_unfair": " وتشير الأهداف المتوقعة ({xg_h}-{xg_a}) إلى أن {better} كان يستحق أكثر.",
        "goals": " الأهداف: {goals}.",
        "no_goals": " ولم ينجح أي فريق في هز الشباك.",
        "control": " سيطر {dom} على الكرة (استحواذ {pos}%) ونجح في {comp}% من تمريراته.",
        "save": " تصدّي المباراة: {keeper} يمنع فرصة بقيمة {xg} xG في الدقيقة {minute}.",
        "potm": " أفضل لاعب في المباراة: {player} ({team}).",
    },
}

TYPE_NAMES = {
    "en": {"pass": "pass", "shot": "shot", "tackle": "tackle", "carry": "carry", "pressure": "pressure",
           "possession_change": "turnover", "foul": "foul", "goal": "goal", "save": "save"},
    "ar": {"pass": "تمريرة", "shot": "تسديدة", "tackle": "تدخّل", "carry": "انطلاقة", "pressure": "ضغط",
           "possession_change": "فقدان للكرة", "foul": "خطأ", "goal": "هدف", "save": "تصدٍّ"},
}
SAFE = {"en": "{clock} {player} ({team}): {kind}.", "ar": "{clock} {player} ({team}): {kind}."}


def pick(options: list[str], key: str) -> str:
    return options[zlib.crc32(key.encode()) % len(options)]

# Spanish, French and Portuguese live in their own module to keep this file readable.
from . import templates_intl as _intl  # noqa: E402

for _name in ("LINES", "ZONES", "FAVOURITE", "MOMENTS", "RECAP", "TYPE_NAMES", "SAFE"):
    globals()[_name].update(getattr(_intl, _name))

LANGS = ("en", "ar", "es", "fr", "pt", "ru")
