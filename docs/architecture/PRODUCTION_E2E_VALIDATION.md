# Production End-to-End Validation Foundation

## Overview
The Production End-to-End (E2E) Validation Foundation provides a safe and repeatable mechanism to verify the entire AI Video OS pipeline using real external services (OpenAI, YouTube) instead of mocks.

## Goals
- Verify end-to-end integration from text generation to YouTube publishing.
- Ensure safety by enforcing private-only uploads to YouTube.
- Provide a clear validation report for stakeholders.
- Prevent accidental execution in non-production environments.

## Architecture

### Components
1. **ValidationRunner**: Orchestrates the flow by creating a dedicated validation workflow, executing it, performing async publishing polling/wait, and validating strict privacy.
2. **VisualValidator**: Uses FFmpeg to extract frames from generated videos and verify they are not black or blank.
3. **E2E Script**: A CLI entry point for manually triggering the validation.

### Validation Flow
1. **Setup**: Create a temporary workflow with a fixed sequence (Text -> Image -> Video) and forced private publishing config.
2. **Execution**: Run the workflow using `WorkflowRuntimeService`.
3. **Visual Check**: Extract a frame from the resulting video asset and perform a non-black check.
4. **Publishing Wait & Check**: Poll publication status with timeout (60s) until `PUBLISHED` or `FAILED`. Ensure strict `privacyStatus == private` assertion passes.
5. **Reporting**: Generate a JSON report summarizing findings without exposing secrets.

## Safety & Security
- **Explicit Opt-in**: Requires `AI_VIDEO_OS_RUN_PRODUCTION_E2E=true` environment variable.
- **Mandatory Private Status**: The validation workflow forces `privacyStatus: private` for YouTube uploads.
- **Secret Redaction**: The validation report strictly excludes any API keys, tokens, or encryption keys.

## Usage
To run the production E2E validation:
```bash
export AI_VIDEO_OS_RUN_PRODUCTION_E2E=true
python scripts/production_e2e_validation.py
```

## Verification
- Unit tests cover the opt-in logic and safety enforcement.
- Integration tests simulate the entire flow using mocks to ensure the foundation is sound.
