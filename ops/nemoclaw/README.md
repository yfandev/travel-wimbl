# NemoClaw / OpenShell integration notes

NemoClaw/OpenShell CLI commands and policy schemas can change. Follow NVIDIA's current official [NemoClaw instructions](https://www.nvidia.com/en-us/ai/nemoclaw), then adapt `policy.example.yaml` to the installed release. The example is a policy design sketch, not a guaranteed drop-in configuration.

## Intended deployment model
- Run long-lived discovery/planning/verifier workers inside a NemoClaw-managed OpenShell sandbox.
- Allow only necessary outbound destinations (You.com and Crusoe inference) where supported.
- Keep provider secrets on the host or in the supported gateway secret store; never mount `.env` into the agent sandbox.
- Restrict filesystem/process access and smoke-test denied network destinations.
- Require explicit human approval for booking, payment, login, or other irreversible actions. Booking is not implemented in this scaffold.

## Bootstrap
1. Install NemoClaw using the current official guide.
2. Create a sandbox for the selected agent framework using the installed CLI.
3. Translate/review the policy sketch for that version.
4. Allow only the required endpoint hosts; avoid wildcard egress.
5. Verify that required endpoints work and unrelated destinations are blocked.
6. Verify API keys are not readable from the sandbox filesystem or prompts.
