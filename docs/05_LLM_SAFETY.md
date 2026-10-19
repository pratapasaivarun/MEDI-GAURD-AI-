# LLM safety check

The deterministic Python rules calculate payable amounts and the comparison engine determines the status and appeal gate. The LLM receives the completed result only to produce explanatory text. The application validates the model response and falls back to a fixed template if the model is down, times out, returns malformed content, or introduces unsupported numeric facts.

The three fictional demo cases were run with Ollama off and with the local `ibm/granite4.1:8b` model available. For each case, the rules status, rule payable, comparison status, expected and actual patient share, difference, decision status, and appeal availability were identical between runs. Case A's explanation passed validation. Case B's generated explanation was rejected and the template was used. Case C stayed in manual review and did not call the model.

Automated checks cover unavailable model, timeout, malformed response, unsupported numbers, and no mutation of comparison amounts/status. The live parity record is in [MILESTONE_LOG.md](MILESTONE_LOG.md). This verifies the prototype path and these fixtures only; it is not a general guarantee for every future prompt or model.
