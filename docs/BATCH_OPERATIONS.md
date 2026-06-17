# Batch Operations

Sprint Q adds controlled batch execution for archive maintenance.

Batch operations are user initiated. Audio Division does not execute batches automatically and does not modify archive contents at startup.

## Execution Model

1. User filters or selects Archive Opportunities.
2. Audio Division maps opportunity categories to supported operations.
3. The batch engine collects album targets from Library path resolution.
4. Ineligible albums are skipped with a reason.
5. Eligible targets execute sequentially through `audio_division.operation_runner`.
6. Results are recorded in `data/operation_history.json`.
7. A summary can be written to `reports/batch_operation_report.md`.

## Supported Operations

- Generate NFO
- Generate SFV
- Validate Albums
- Open Album Folders

The first three require confirmation in the GUI before execution.

## Safety Controls

The GUI confirms:

- operation
- album count
- target count

Operations use existing configured tool paths. The batch layer does not call subprocesses directly.

## Failure Handling

Failures do not abort a batch. Each target result is recorded and the batch continues.

The final summary includes:

- total
- successes
- failures
- skipped
- duration

## History Integration

Each operation history entry may include:

- `batch_id`
- `operation`
- `target`
- `result`
- `message`

This allows batch runs to be reconstructed from operation history.

## Future Expansion

Possible future work:

- Queue Manager
- Scheduled Maintenance
- Nightly Validation
- Repair Workflows
- Archive Campaigns
