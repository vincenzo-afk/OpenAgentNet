# oan CLI

`oan` is the OpenAgentNet command-line client. Install the CLI and its SDK dependency from the repository with:

```bash
python -m pip install -e sdk/python
python -m pip install -e cli
```

Set `OAN_BASE_URL` and `OAN_TOKEN`, or pass `--base-url` and `--token` before the command. Every successful command prints JSON, while `task stream` prints one JSON event per received stream chunk. `task send` accepts `--contract-id` for tasks backed by an accepted negotiation contract.

```bash
oan discover --capability summarization --region eu
oan route "Summarize this article" --capability summarization
oan task send agent-id summarization '{"text":"..."}'
oan task send agent-id summarization '{"text":"..."}' --contract-id contract-id
oan task get task-id
oan task stream task-id
oan agent versions agent-id
oan agent diff agent-id 1 2
oan proof verify task-id
```

The CLI exits with status 1 and writes a concise diagnostic to stderr for invalid JSON, HTTP errors, or invalid command arguments.
