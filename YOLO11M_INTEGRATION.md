# Satellite YOLO11m V1 integration

The default profile is `yolo11m_v1`, checkpoint
`models/yolo11m_olivesmart_v1.pt`. Its SHA-256 is
`31B226A7FB9BCFD2AD7803DB79472CAD6581299819FEF6AF2DA80E0DE81E4757`.
The original root `best.pt` is preserved. Source backups are in
`backups/yolo11m-integration-20261113-135222/`.

## Selection and rollback

Profiles are defined in `model_config.py` and read once at Python process startup.
No model or dependency is automatically downloaded. Missing or invalid selections
fail explicitly and never select a different model. A failed startup load requires
correcting the problem and restarting Python.

To return to the historical model, stop the existing Python service, then run from
the project root in PowerShell:

```powershell
$env:OLIVESMART_MODEL = 'yolov8n'
& .\.venv\Scripts\python.exe -B ai_engine_server.py
```

This selects root `best.pt`, with `imgsz=640`, `conf=0.10`, `iou=0.35`,
`max_det=300`, `device=cpu`. To select the new profile again, stop Python and use:

```powershell
$env:OLIVESMART_MODEL = 'yolo11m_v1'
& .\.venv\Scripts\python.exe -B ai_engine_server.py
```

The new profile uses `imgsz=1280`, `conf=0.20`, `iou=0.50`, `max_det=1000`,
`device=cpu`, including during warmup. Existing Java and browser clients do not
select weights; the Python process configuration is authoritative.

## Compatible response and two distinct results

All existing fields and endpoints remain. `trees` and `totalTrees` still refer to
the final HYBRID result displayed on the map. The optional `analysisMetadata`
object passes unchanged through Java and contains:

- `yoloRawTrees`: all predictions on the padded crop after YOLO thresholds/NMS,
  before OpenCV, with unchanged box coordinates in mosaic pixels, GPS bounds,
  confidence, and `insideParcel`. No health labels are assigned to raw boxes.
- `yoloRawCount`: all those predictions, including centers outside the polygon.
- `yoloInPolygonCount`: only raw predictions whose center lies in the polygon.
  This is the raw YOLO count comparable to the hybrid parcel count.
- `hybridCount`: final count after existing OpenCV recovery/filtering/merging.
- Model path/profile, inference parameters, tile count, timings, and health method.

The browser shows raw YOLO-in-parcel and hybrid counts separately. Raw boxes are
available through the API metadata; the existing map continues to display hybrid
boxes. The old clients can ignore the new field. Older Python responses without
metadata still deserialize in Java.

ExG labels are unchanged computationally. They are visual heuristics, not validated
health, disease or water-stress predictions. The LIVE tree panel no longer shows
invented disease probabilities or disease-specific prescriptions. Historical
experiments and drone upload algorithms are preserved.

## CPU limits and errors

One analysis runs at a time; another request receives explicit HTTP 503.
Requests exceeding 7 by 7 Esri tiles are rejected instead of silently truncated.
The 45-second cooperative budget is checked between tile downloads and processing
stages. It cannot interrupt a running native YOLO/OpenCV call. Java retains its
60-second timeout and the existing explicit failure response; HTTP errors from
Python are relayed without generating simulated results. There is no automatic
fallback to another model. `/health` reports the selected model and load error.

## Verification

Existing test logic was not changed. New regression tests cover profile selection,
inference arguments, raw/hybrid distinction, missing-checkpoint behavior, CPU
admission and additive Java JSON metadata.

Python and Node:

```powershell
& .\.venv\Scripts\python.exe -B -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/traceability.test.cjs
```

Java requires JDK 17 or newer. In this environment Maven otherwise selects Java 8;
the following changes environment variables only for the current terminal. The
JUnit version override uses the already cached 5.10.1 artifacts, without changing
the POM or downloading dependencies:

```powershell
$env:JAVA_HOME = 'C:\Program Files\Eclipse Adoptium\jdk-21.0.13.9-hotspot'
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
mvn -o '-Dmaven.repo.local=C:\Users\pc\.m2\repository' '-Djunit-jupiter.version=5.10.1' -f springboot-microservice-olive/pom.xml test
```

`tools/verify_satellite_integration.py` starts isolated loopback servers on temporary
ports, analyzes one real Esri parcel, checks actual predictor arguments and Java
metadata propagation, then stops its servers. It requires the preceding Java tests
to have produced the cached classpath report. It can fetch one Esri tile into the
normal cache, but installs nothing. The result is saved to
`resultats_tests/yolo11m_satellite_integration.json`.

Initial real test: 34 raw crop boxes, 15 raw centers inside the parcel, 25 hybrid
trees. Weight loading 610.3 ms (excluding warmup); YOLO inference 2803.1 ms;
Python analysis 3303 ms; complete Java/Python HTTP round trip 3727.7 ms. These are
single-parcel observations, not accuracy metrics or a latency guarantee. CPU-only
execution, 20,053,779 model parameters, class `trees`.

Production servers were not started or restarted. Restart existing services from
the updated sources before using the integration. If using a packaged JAR, rebuild
it first; an older JAR will omit the new metadata. Do not run the historical HTML
generator. No dependency, database or drone inference change was made.
