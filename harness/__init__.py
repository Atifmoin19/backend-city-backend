"""Backend City harness — runs a game's backend + the learner's snippet in-process.

SHARED CODE: these files are copied into the frontend and executed inside Pyodide, and
also run on the server inside the grading sandbox. Therefore:
  * Pure Python only; depends only on fastapi/pydantic (versions pinned in requirements.txt
    to match the Pyodide distribution).
  * NEVER put hidden tests, reference solutions, or variant generation logic here —
    everything in this folder is public.
"""

HARNESS_VERSION = "0.2.0"
