# Evaluation

This folder holds fictional ground-truth labels, reviewer-confirmed synthetic policy terms, retrieval annotations, scripts, and the latest generated measurements. From the repository root, run `python evaluation/scripts/run_evaluation.py --repeats 1`, then `python evaluation/scripts/run_system_evaluation.py --rules-only`, then `python evaluation/scripts/score_annotations.py`; generated JSON and CSV files go in `latest/`. These are synthetic-only measurements.
