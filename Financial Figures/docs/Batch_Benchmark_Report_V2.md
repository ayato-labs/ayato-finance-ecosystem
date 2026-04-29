# True Batching Benchmark Report (V2)

**Model**: gemma-4-26b-a4b-it
**Date**: Sat Apr 18 17:18:45 2026

| Batch Size | Total Duration (s) | Throughput (s/tag) | Success Rate |
|------------|--------------------|--------------------|--------------|
| 1 | 2.77 | 2.765 | 100.0% |
| 5 | 7.94 | 1.589 | 100.0% |
| 10 | 10.13 | 1.013 | 100.0% |
| 15 | 20.44 | 1.363 | 100.0% |
| 20 | 18.76 | 0.938 | 100.0% |
| 30 | 23.19 | 0.773 | 100.0% |

## Conclusion
Optimal batch size for throughput is **30** with **0.773s/tag**.
