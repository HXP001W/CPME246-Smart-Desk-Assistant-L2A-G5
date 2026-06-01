# Logging and Report Generation

The project uses structured JSONL logging to connect independent modules together.

## Why Logging Matters

The system has multiple modules:

- UI/session manager
- distraction detector
- hardware controller
- report generator

Instead of each module storing information differently, all modules write structured events using the shared logger. This makes it possible to reconstruct a study session later.

## `logger.py`

`logger.py` defines the shared logging system.

### `create_session_id()`

Creates a readable ID such as:

```text
2026-04-01_14-30-00_study_session
```

All modules use the same session ID so their logs can be merged.

### `EventLogger`

`EventLogger` writes one JSON object per line into a `.jsonl` file.

Each module writes to a separate file:

```text
logging/logs/<session_id>_<module_name>.jsonl
```

For example:

```text
logging/logs/2026-04-01_14-30-00_study_session_distraction_detection.jsonl
logging/logs/2026-04-01_14-30-00_study_session_session_manager.jsonl
logging/logs/2026-04-01_14-30-00_study_session_hardware_control.jsonl
```

## Event Format

Each event can include:

| Field | Meaning |
|---|---|
| `timestamp` | Real wall-clock time |
| `session_id` | Shared session ID |
| `module` | Module that created the event |
| `event_type` | Type of event |
| `value` | Main event value |
| `details` | Extra structured information |
| `session_elapsed_seconds` | Time since logger started |
| `since_previous_event_seconds` | Time since previous event in that module |
| `user_id` | Optional user ID |
| `user_name` | Optional user name |
| `event_duration_seconds` | Optional duration |

## Example Events

### State update

```json
{
  "event_type": "state_update",
  "value": "DISTRACTING APP",
  "details": {
    "attention_state": "FOCUSED",
    "posture_state": "OK",
    "phone_present": false,
    "app_focus_state": "DISTRACTING_APP"
  }
}
```

### Water pump trigger

```json
{
  "event_type": "water_pump_triggered",
  "value": "triggered",
  "details": {
    "reason": "DISTRACTING APP",
    "pulse_seconds": 1.0
  }
}
```

## `report_generator.py`

`report_generator.py` reads the logs for one session and summarizes them.

### Main Steps

1. Load all log files matching the session ID.
2. Parse each JSONL event.
3. Count event types.
4. Count distraction reasons.
5. Calculate total study duration.
6. Calculate total distraction time.
7. Calculate total bad posture time.
8. Count pump triggers.
9. Save a summary JSON file.
10. Generate an HTML report for the UI.

## Summary Metrics

The generated report includes:

- session ID
- user name
- total event count
- study duration
- break count
- break duration
- distraction duration
- bad posture duration
- water pump trigger count
- distraction reasons
- event duration totals

## How the UI Uses Reports

`UI.py` uses `logger.py` to find sessions for the current user.

When the user opens a report page:

1. `UI.py` checks whether a saved report summary exists.
2. If not, it uses `report_generator.py` to generate one.
3. The report generator returns HTML.
4. The Flask UI embeds that HTML into the report page.
