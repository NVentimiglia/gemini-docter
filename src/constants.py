import re

TRANSCRIPTS_DIR = ".gemini-docter/transcripts"

ABANDONMENT_WINDOW_MS = 30 * 60 * 1000
SHORT_SESSION_THRESHOLD = 3
SHORT_SESSION_RATIO_THRESHOLD = 0.3
SHORT_SESSION_RATIO_CRITICAL = 0.5
MIN_SHORT_SESSIONS_TO_FLAG = 3

THRASHING_EDIT_THRESHOLD = 5
THRASHING_SEVERITY_CRITICAL = 20
THRASHING_SEVERITY_HIGH = 10

ERROR_LOOP_THRESHOLD = 3
ERROR_LOOP_CRITICAL_THRESHOLD = 5
ERROR_SNIPPET_MAX_LENGTH = 200

READ_TO_EDIT_RATIO_THRESHOLD = 10
READ_TO_EDIT_RATIO_HIGH = 20
READ_ONLY_SESSION_THRESHOLD = 20
READ_ONLY_SESSION_SCORE = -5

MAX_USER_MESSAGE_LENGTH = 2000

SENTIMENT_FRUSTRATION_THRESHOLD = -2
SENTIMENT_NEGATIVE_THRESHOLD = -1
SENTIMENT_CRITICAL_THRESHOLD = -3
SENTIMENT_HIGH_THRESHOLD = -2
SENTIMENT_EXTREME_THRESHOLD = -5
INTERRUPT_SCORE_MULTIPLIER = 2
INTERRUPT_CRITICAL_THRESHOLD = 3

CORRECTION_RATE_THRESHOLD = 0.2
CORRECTION_RATE_CRITICAL = 0.4
MIN_CORRECTIONS_TO_FLAG = 2
CORRECTION_SCORE_MULTIPLIER = 3

KEEP_GOING_MIN_TO_FLAG = 2
KEEP_GOING_HIGH_THRESHOLD = 4
KEEP_GOING_SCORE_MULTIPLIER = 2

REPETITION_SIMILARITY_THRESHOLD = 0.6
REPETITION_LOOKAHEAD_WINDOW = 5
MIN_REPETITIONS_TO_FLAG = 2
REPETITION_CRITICAL_THRESHOLD = 4
REPETITION_SCORE_MULTIPLIER = 3

DRIFT_MIN_MESSAGES = 4
DRIFT_NEGATIVE_THRESHOLD = 2
DRIFT_HIGH_THRESHOLD = 5
DRIFT_LENGTH_WEIGHT = 5
DRIFT_CORRECTION_WEIGHT = 10
DRIFT_SCORE_MULTIPLIER = 2

RAPID_FOLLOWUP_MS = 10_000
RAPID_FOLLOWUP_MAX_MS = 3_600_000
MIN_RAPID_FOLLOWUPS_TO_FLAG = 3
RAPID_FOLLOWUP_HIGH_THRESHOLD = 5
RAPID_FOLLOWUP_SCORE_MULTIPLIER = 2

HIGH_TURN_RATIO_THRESHOLD = 1.5
HIGH_TURN_RATIO_HIGH = 2.5
MIN_USER_TURNS_FOR_RATIO = 5
TURN_RATIO_SCORE_MULTIPLIER = 2

SUGGESTION_EDIT_THRASHING_MIN = 2
SUGGESTION_ERROR_LOOP_MIN = 3
SUGGESTION_SENTIMENT_MIN = 3
SUGGESTION_INTERRUPTS_MIN = 2
SUGGESTION_RESTART_MIN = 2
SUGGESTION_EXPLORATION_MIN = 3
SUGGESTION_READ_ONLY_MIN = 3
SUGGESTION_CORRECTION_MIN = 2
SUGGESTION_KEEP_GOING_MIN = 2
SUGGESTION_REPETITION_MIN = 2
SUGGESTION_DRIFT_MIN = 2
SUGGESTION_RAPID_MIN = 2
SUGGESTION_TURN_RATIO_MIN = 2

SEVERITY_WEIGHT_CRITICAL = 4
SEVERITY_WEIGHT_HIGH = 3
SEVERITY_WEIGHT_MEDIUM = 2
SEVERITY_WEIGHT_LOW = 1

TOP_SIGNALS_LIMIT = 20
REPORT_PROJECT_LIMIT = 10
REPORT_SIGNAL_DISPLAY_LIMIT = 15
EXAMPLE_TRUNCATE_LENGTH = 120
SNIPPET_LENGTH = 60
EXAMPLE_REFERENCE_THRESHOLD = 5

HEALTH_GOOD_THRESHOLD = 80
HEALTH_FAIR_THRESHOLD = 50

SAVED_MODEL_VERSION = 1

SENTINEL_CUSTOM_TOKENS: dict[str, float] = {
    "undo": -3,
    "revert": -3,
    "wrong": -3,
    "incorrect": -3,
    "rollback": -3,
    "start": -2,
    "over": -2,
    "try": -1,
    "again": -1,
    "broken": -2,
    "shit": -3,
    "fuck": -4,
    "damn": -2,
}

INTERRUPT_PATTERN = re.compile(r"\[Request interrupted by user")

META_MESSAGE_PATTERNS = [
    re.compile(r"^<local-command"),
    re.compile(r"^<command-name>"),
    re.compile(r"^<environment>"),
    re.compile(r"^<task-notification"),
    re.compile(r"^```"),
]

EDIT_TOOL_NAMES = [
    "write_file",
    "replace_file_content",
    "multi_replace_file_content",
    "edit_file",
    "create_file",
    "str_replace",
    "patch_file",
    "overwrite_file",
]

READ_TOOL_NAMES = [
    "read_file",
    "view_file",
    "list_directory",
    "ls",
    "grep_search",
    "glob",
    "search_files",
    "find_files",
    "list_files",
]

CORRECTION_PATTERNS = [
    re.compile(r"^no[,.\s!]", re.IGNORECASE),
    re.compile(r"^nope", re.IGNORECASE),
    re.compile(r"^wrong", re.IGNORECASE),
    re.compile(r"^that'?s not", re.IGNORECASE),
    re.compile(r"^not what i", re.IGNORECASE),
    re.compile(r"^i (said|meant|asked|wanted)", re.IGNORECASE),
    re.compile(r"^actually[,\s]", re.IGNORECASE),
    re.compile(r"^wait[,\s]", re.IGNORECASE),
    re.compile(r"^stop", re.IGNORECASE),
    re.compile(r"^instead[,\s]", re.IGNORECASE),
    re.compile(r"^don'?t do that", re.IGNORECASE),
    re.compile(r"^why did you", re.IGNORECASE),
]

KEEP_GOING_PATTERNS = [
    re.compile(r"^keep going", re.IGNORECASE),
    re.compile(r"^continue", re.IGNORECASE),
    re.compile(r"^keep at it", re.IGNORECASE),
    re.compile(r"^more$", re.IGNORECASE),
    re.compile(r"^finish", re.IGNORECASE),
    re.compile(r"^go on", re.IGNORECASE),
    re.compile(r"^don'?t stop", re.IGNORECASE),
    re.compile(r"^you'?re not done", re.IGNORECASE),
    re.compile(r"^not done", re.IGNORECASE),
    re.compile(r"^keep iterating", re.IGNORECASE),
]
