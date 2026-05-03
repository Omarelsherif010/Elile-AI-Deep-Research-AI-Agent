# Test Fixtures

This directory contains recorded HTTP responses and LLM response fixtures for use in integration tests.

## cassette_synthetic_target.json
HTTP cassette for one synthetic target ("Alexandra Chen"). Contains:
- Brave Search API responses (mocked)
- Page content responses (mocked)

## llm_responses/
Recorded LLM responses for each node in the pipeline:
- planner_response.json
- extractor_response.json
- validator_response.json
- reflector_terminate_response.json
- risk_analyzer_response.json
- reporter_response.json
