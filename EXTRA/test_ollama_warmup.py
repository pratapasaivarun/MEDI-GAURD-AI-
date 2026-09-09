import time
from agents import warm_ollama, OLLAMA_MODEL, OLLAMA_TIMEOUT

started = time.time()
warm_ollama()
print('model=', OLLAMA_MODEL)
print('timeout_seconds=', OLLAMA_TIMEOUT)
print('warmup_seconds=', round(time.time() - started, 2))
print('OLLAMA_WARMUP_TEST_OK')
