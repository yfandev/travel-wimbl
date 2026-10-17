# Configure You.com for Wimbl

Wimbl uses the **You.com Web Search API** for the first live-search integration.

Official docs:
- [Web Search API reference](https://you.com/docs/api-reference/search/v1-search)
- [API authentication](https://you.com/docs/using-the-api/authentication)
- [Get an API key](https://you.com/platform)

## Exact setup

1. Sign in at [You.com Platform](https://you.com/platform) and create/copy an API key with **Web Search API** access.
2. In the root of your local clone of this repository, copy `.env.example` to `.env`.
3. Edit `.env` and set these values:

```dotenv
YOU_API_KEY=paste_your_real_key_in_your_local_env_file
YOU_SEARCH_ENDPOINT=https://ydc-index.io/v1/search
WIMBL_DEMO_MODE=false
```

Replace the placeholder with your key **locally only**. Do not paste the key into ChatGPT, an issue, a pull request, or a source file. The repository ignores `.env`; never force-add it.

## Test the connection

From the repository root, install dependencies and run:

```bash
pip install -r requirements.txt
python scripts/check_youcom.py
```

The check sends one search request and prints the result titles and URLs, never the API key. This may consume one API request/credit according to your plan.

Expected success: `SUCCESS: received N result(s)` followed by result titles and URLs. Common failures:
- `401`: key missing, invalid, or copied incorrectly.
- `402`: billing/credits/plan issue.
- `403`: key does not have the required Web Search API scope.
- `422`: request body or parameter mismatch.
- Network/timeout: check connectivity and the current service status.

## What I need from you

You do **not** need to give me the secret itself. Please provide only:
- Confirmation that you have a You.com **Web Search API** key (or tell me if your key is for Answer, Research, or MCP instead).
- The non-secret output from `python scripts/check_youcom.py` if it fails (HTTP status and error message; remove request IDs if you prefer).

If the key is only available to you in a hosted environment, tell me where Wimbl will run (local laptop, GitHub Actions, or a deployment host); the key should be stored in that environment's secret manager, not committed to GitHub.
