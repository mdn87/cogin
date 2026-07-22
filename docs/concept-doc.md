Taxonomy Bench



I converted the repository into a runnable AI session-strength benchmark.



The Marble dataset is well suited to this because it provides 1,590 fine-grained topics connected by 3,221 prerequisite edges in a directed acyclic graph, along with descriptions, evidence criteria, subject classifications, age ranges, and edge-strength labels.



Download the complete Taxonomy Bench package



Individual files:



README.md

taxonomy\_bench.py

BENCHMARK\_SPEC.md

Installable Python wheel

VALIDATION.md

Package SHA-256 checksum

What the test measures



Each seeded suite has eight progressively harder tiers:



Semantic topic identification

Direct prerequisite extraction

Reverse dependency and bounded transitive reasoning

Topological ordering

Shortest-path graph reasoning

Minimal mastery planning

Larger multi-constraint graph tasks

Planning and integrity auditing under maximum benchmark complexity



The primary results are:



base\_strength\_0\_100: difficulty-weighted exact performance on first attempts

eventual\_strength\_0\_100: the same score after allowed retries

retry\_lift\_points: improvement produced by retries

retry\_recovery\_rate: proportion of first-attempt failures successfully corrected

reliable\_frontier\_first: highest consecutive tier where at least two-thirds of tasks pass

median and p90 first-attempt latency

cumulative time to the first correct response

weighted points per minute

weighted points per 1,000 output tokens

strict JSON and recoverable JSON rates

reasoning, input, cached-input, output, and total token use

requested and provider-resolved model IDs

infrastructure-error and scored-coverage measurements



It deliberately reports a profile rather than pretending that one number is general intelligence. The base score is the closest thing to a current-session strength index. The frontier shows how far the session reliably gets, while latency and token efficiency show how fast and computationally expensive that performance is.



Retry comparison



A run with retries automatically produces a paired comparison.



All first attempts are completed before any cognitive retry begins. This means:



First-attempt results are the effective no-retry condition.

Eventual results are the with-retries condition.

Early retry feedback cannot contaminate later first attempts.

A separate no-retry execution is not required for the basic comparison.



Retry conditions can be varied independently:



Blind retry versus diagnostic feedback

Fresh retry context versus continued conversation context

Zero, one, or multiple retries

Isolated task sessions versus one continuous session

Prompt-only JSON versus schema-enforced output

Cognitive retries versus transport retries



The OpenAI adapter explicitly sets transport retries to zero by default because the Python SDK otherwise retries selected transport failures automatically. It also records reasoning-token usage, supports Structured Outputs, and can use previous\_response\_id for genuine continued-context retries.



Comparing models and effort levels



The matrix command runs the same hidden suite across model, effort, and repeat combinations:



python taxonomy\_bench.py matrix \\

&#x20; --suite suites/taxonomy-v1-seed42.private.json \\

&#x20; --provider openai \\

&#x20; --models MODEL\_ID\_A,MODEL\_ID\_B \\

&#x20; --efforts low,medium,high \\

&#x20; --repeats 3 \\

&#x20; --session isolated \\

&#x20; --retries 2 \\

&#x20; --retry-policy feedback \\

&#x20; --retry-context continued \\

&#x20; --output-mode schema \\

&#x20; --transport-retries 0 \\

&#x20; --out matrix-runs



Effort values are passed through rather than hard-coded because supported reasoning-effort levels vary by model. Lower effort generally favors latency and token use, while higher effort permits more reasoning work.



The generated matrix.html ranks runs by first-attempt strength and then latency. Individual repeats remain visible so variance is not concealed by an average.



Basic usage



Clone the taxonomy into a sibling directory, unpack the benchmark, and run:



cd taxonomy-bench



python taxonomy\_bench.py validate \\

&#x20; --taxonomy ../os-taxonomy \\

&#x20; --verify-checksums



python taxonomy\_bench.py generate \\

&#x20; --taxonomy ../os-taxonomy \\

&#x20; --seed 42 \\

&#x20; --max-tier 8 \\

&#x20; --tasks-per-tier 4 \\

&#x20; --out suites/taxonomy-v1-seed42.private.json



Run one API model:



pip install -e ".\[openai]"

export OPENAI\_API\_KEY="..."



python taxonomy\_bench.py run \\

&#x20; --suite suites/taxonomy-v1-seed42.private.json \\

&#x20; --provider openai \\

&#x20; --model MODEL\_ID \\

&#x20; --effort medium \\

&#x20; --session isolated \\

&#x20; --retries 2 \\

&#x20; --retry-policy feedback \\

&#x20; --retry-context continued \\

&#x20; --output-mode prompt \\

&#x20; --transport-retries 0 \\

&#x20; --tool-access none \\

&#x20; --out runs



Each run produces:



summary.json

run.json

attempts.jsonl

report.html

suite.private.json

suite.public.jsonl



The source repository’s validator checks endpoint references, self-dependencies, hard and soft edge strengths, standard references, declared counts, and file checksums. The benchmark preserves those checks and adds DAG validation, hidden-suite hashing, and deterministic task generation.



Testing the current ChatGPT or another UI session



The generator emits a public prompt JSONL and a response-template JSONL. The private suite contains the answer keys and must remain inaccessible to the tested session.



For a continuous-session test, submit every public prompt in order to the same conversation. For an isolated test, use a fresh conversation for each prompt. Record responses as:



{

&#x20; "task\_id": "t01-01-semantic\_match",

&#x20; "attempt": 1,

&#x20; "text": "{\\"id\\":\\"mt\_...\\"}",

&#x20; "latency\_ms": 1820

}



Retries use contiguous attempt numbers:



{

&#x20; "task\_id": "t01-01-semantic\_match",

&#x20; "attempt": 2,

&#x20; "text": "{\\"id\\":\\"mt\_corrected\\"}",

&#x20; "latency\_ms": 1460

}



Then score the session:



python taxonomy\_bench.py score \\

&#x20; --suite suites/taxonomy-v1-seed42.private.json \\

&#x20; --responses responses.jsonl \\

&#x20; --model "ChatGPT UI session" \\

&#x20; --effort "selected UI effort" \\

&#x20; --source manual-session \\

&#x20; --tool-access "web, python" \\

&#x20; --out scored-runs

Validation status



The delivered package passed:



Six automated tests

Exact oracle scoring across all eight tiers

Paired first-attempt and retry-recovery tests

Private-suite tamper detection

Manual retry-sequence validation

Generation fuzzing across 50 additional seeds

Clean wheel installation

CLI validation and generation smoke tests

Checksum verification after extracting the final ZIP



The included synthetic fixture has 64 topics and 156 dependencies, allowing the complete benchmark to be tested without redistributing Marble’s data.



A full local execution against the upstream 1,590-topic dataset was not possible in this sandbox because direct GitHub cloning was blocked by DNS restrictions. The repository structure, schemas, source validation code, topic records, and dependency records were inspected through the GitHub connector. The package intentionally excludes upstream data and embeds the required attribution in generated reports because the database and authored content use ODbL 1.0 and CC BY-SA 4.0 respectively.



ZIP SHA-256:



2bd216e0b977baebc2bf94753a147696ab4fefe888c7ca64e1c2ed0d8c29366e

