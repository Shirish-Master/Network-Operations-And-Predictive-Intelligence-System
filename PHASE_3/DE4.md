# DE4 – Batch vs Streaming Decision Analysis

## 1. Classify: daily usage summary, hypothetical live activity events, billing report, hotspot alerts, executive dashboard refresh, and model training and scoring.

### Decision Matrix

| Workload | Classification |
|-----------|-----------|
| Daily Usage Summary | Batch |
| Hypothetical Live Activity Events | Streaming |
| Billing Report | Batch |
| Hotspot Alerts | Streaming |
| Executive Dashboard Refresh | Batch |
| Model Training | Batch |
| Model Scoring | Streaming |

---

## 2. For each, document the source, arrival pattern, required latency, and the batch-or-streaming decision.

| Workload | Source | Arrival Pattern | Required Latency | Decision |
|-----------|-----------|-----------|-----------|-----------|
| Daily Usage Summary | Telecom usage CSV files | Daily | Hours | Batch |
| Hypothetical Live Activity Events | Network activity events | Continuous | Seconds | Streaming |
| Billing Report | Historical usage records | Daily / Monthly | Hours to Days | Batch |
| Hotspot Alerts | Network traffic monitoring system | Continuous | Seconds | Streaming |
| Executive Dashboard Refresh | Aggregated telecom metrics | Scheduled refresh | Minutes to Hours | Batch |
| Model Training | Historical telecom activity data | Periodic datasets | Hours | Batch |
| Model Scoring | Incoming activity events | Continuous | Seconds | Streaming |

---

## 3. Identify where Kafka could conceptually enter the architecture, without changing this training dataset.

### Current Training Architecture

```text
Landing Files
      |
      v
data/landing
      |
      v
Ingestion (DE2)
      |
      v
data/raw
      |
      v
telecom_pipeline.py
      |
      v
data/processed
      |
      v
data/analytics
```

### Revised Architecture with Optional Streaming Path (Conceptual Only)

```text
                         +------------------+
                         | Live Network     |
                         | Activity Events  |
                         +------------------+
                                   |
                                   v
                                Kafka
                                   |
                                   v
                     Real-Time Consumers
                                   |
                                   v
                     Streaming Scoring / Alerts


Landing Files
      |
      v
data/landing
      |
      v
Ingestion (DE2)
      |
      v
data/raw
      |
      v
telecom_pipeline.py
      |
      v
data/processed
      |
      v
data/analytics
```

Kafka is introduced only as a conceptual streaming component and does not replace the existing file-based training dataset.

---

## 4. Discuss why these files are processed as batch even though real network activity is continuous.

Real telecom network activity is generated continuously by users and network devices. However, this training project receives activity data as CSV files rather than as individual real-time events.

Batch processing is used because:

- Input data arrives in files rather than event streams.
- Historical analysis does not require second-level response times.
- Data quality validation is easier on complete datasets.
- Batch processing is simpler to develop, test, and troubleshoot.
- Daily summaries and reporting workloads naturally fit batch processing patterns.
- The training environment focuses on batch data engineering concepts before introducing streaming technologies.

Therefore, although real telecom activity is continuous, the project processes the data as batch workloads because the dataset is delivered in periodic files.

---

## 5. Map batch to model training, and streaming to potential real-time scoring.

### Batch Model Training

```text
Historical Telecom Data
          |
          v
Feature Engineering
          |
          v
Model Training
          |
          v
Trained Model
```

Characteristics:

- Uses large historical datasets.
- Periodically retrains models.
- Prioritizes accuracy over immediate response time.
- Runs on schedules such as daily, weekly, or monthly.

### Streaming Real-Time Scoring

```text
Live Event
     |
     v
Trained Model
     |
     v
Prediction
     |
     v
Alert / Action
```

Characteristics:

- Evaluates individual events as they arrive.
- Produces near real-time predictions.
- Supports anomaly detection and hotspot detection.
- Enables immediate operational responses.

---

## 6. Present one decision where batch is the better engineering choice, and defend it.

### Decision: Billing Report Generation

Batch processing is the better engineering choice for billing reports.

Reasons:

- Billing calculations require complete and validated usage records.
- Accuracy is more important than real-time processing speed.
- Reports are typically generated daily or monthly.
- Reconciliation and auditing are easier using complete datasets.
- Batch processing reduces infrastructure complexity and operational cost.
- Historical corrections can be incorporated before report generation.

For these reasons, batch processing provides a more reliable and cost-effective solution for billing report generation than streaming.

---

# Expected Output Deliverables

## Decision Matrix

Provided in Question 1 and Question 2.

## Revised Architecture with Optional Streaming Path

Provided in Question 3, showing Kafka as a conceptual streaming component without modifying the existing training dataset.