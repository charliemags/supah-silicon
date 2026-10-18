# Measure Muni before specifying Supah hardware

This harness runs Muni's actual Ruby implementations against bounded public
Cambridge data. It measures JSON decoding, source normalization, SQLite writes,
indexed reads, empirical prediction, digest context/ranking, and preparation of
the existing Anthropic request. **It never calls Anthropic.**

The checked-in results use 5,000 service requests, 5,000 permits, one city-news
item and 60 calendar items. A second run uses the first 1,000 records from each
of the same two municipal datasets. The 311 sample uses Muni's supported
Socrata normalization path, rather than the primary Open311 transport. News and
calendar samples are fetched and normalized by Muni's source classes.

[Read the measured results](RESULTS.md) and [the Supah Edge design proposal](../architecture/README.md).

## Reproduce

Use a Muni checkout with its Ruby dependencies installed. The wrapper defaults
to a sibling `../muni` checkout and uses its Gemfile and Ruby version through
rbenv when available. Otherwise, activate Muni's required Ruby before running.
Commands below run from the `supah-silicon` repository root.

```sh
export SUPAH_MUNI_ROOT=/absolute/path/to/muni
./profiling/run --cache .cache/muni-corpus --output profiling/results/local-5000.json --fetch --rows 5000
./profiling/run --cache .cache/muni-corpus --output profiling/results/local-1000.json --sample-rows 1000
python3 profiling/design.py profiling/results/local-5000.json --output architecture/local-design.json
```

`--fetch` makes bounded public-network reads and refuses to overwrite an
existing corpus manifest. Later runs verify input hashes and replay the local
cache. Use a fresh cache directory for a new capture and a fresh output file
for every measurement. Public sources change over time, so fresh captures are
not byte-identical replays of the checked-in results. Hashes record that
boundary. Raw records, database contents and model prompts stay local in the
ignored cache; only aggregate measurements and input/source hashes are
published here.

All database writes go to a disposable database. The Muni application database
is not used. The harness loads Muni without changing its implementation. It
records the Muni commit, dirty-working-copy flag and hashes of loaded source
files, because a commit alone does not describe a modified checkout.

The default protocol is two warmups followed by seven measured repetitions,
with `GC.start` before each iteration. Natural GC during the work is included.
Wall time, process CPU time, allocated Ruby objects and GC time are recorded.
Database reset/setup, corpus fetch and application boot are outside the local
stage timings. Fetch/decode durations are recorded separately in the corpus
manifest. Fresh inserts and same-value updates are separate workloads. The
bulk operation uses Muni's existing 750-row transaction batches.

Run comparisons under the same execution environment. Sandboxes, emulation,
profilers, concurrent CPU load and different database settings can change the
results substantially. The published measurements used native host execution,
not the Linux thermal-simulator container. The small-run p95 is descriptive,
not a production tail-latency guarantee. No memory-bus counters or power meter
were available, so memory traffic, working-set peak and joules per task remain
unmeasured. JSON payload bytes are not DRAM traffic.

## Generate a hardware hypothesis

`design.py` derives per-operation CPU service demand, the measured batching
comparison and Amdahl upper bounds for accelerating individual ingestion
stages. Its default request rates are explicitly illustrative assumptions.
Supply a JSON file containing all five rates to evaluate another scenario:

```json
{
  "service_request_rows_s": 100,
  "permit_rows_s": 100,
  "queries_s": 10,
  "empirical_predictions_s": 10,
  "digest_requests_s": 0.1
}
```

```sh
python3 profiling/design.py profiling/results/cambridge-5000.json --rates my-rates.json --utilization 0.6 --output architecture/local-design.json
```

This estimates demand on the measured reference host. It does not predict the
core count, performance or power of a new chip, nor account for SQLite writer
contention, Ruby concurrency, production redundancy or generative inference.
The custom-core, SRAM, DRAM-bandwidth, TOPS, area and power fields remain null.

## Check and visualize

```sh
./profiling/run test
python3 -m unittest discover -s profiling/tests -v
```

The Ruby suite covers warmup accounting, preparation boundaries, invalid work
budgets and corpus integrity. Python tests guard work-unit normalization,
missing/duplicate measurements, nonfinite inputs, scenario arithmetic and
unsupported hardware claims.

`plot.py` needs Matplotlib. The existing simulation image provides it:

```sh
./simulation/run setup
docker run --rm --platform linux/amd64 --network none -v "$PWD:/work" supah-silicon-sim:local profiling/plot.py profiling/results/cambridge-5000.json profiling/results/local-chart.png
```

The 2.5D challenge and its frozen workloads remain separate. Real CPU timings
cannot be assigned to its GPU power maps without a calibrated architecture
and power model.
