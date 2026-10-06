# Risk Prediction API Contract

Endpoint: `POST /network/predict-risk`

## Request

The request body must contain:

- `grid_id`: integer from 1 through 10000
- `avg_activity`: non-negative number
- `activity_growth`: number
- `active_hours`: integer from 0 through 24
- `peak_ratio`: non-negative number
- `variability`: non-negative number
- `internet_share`: number from 0 through 1
- `feature_timestamp`: ISO-8601 timestamp

## Response

The response contract is stable for the React client and ML5 replacement:

- `risk_score`: number from 0 through 1
- `risk_level`: string
- `model_version`: string
- `explanation_note`: string
- `feature_timestamp`: ISO-8601 timestamp for the ML2 feature row
- `contributing_features`: optional list of feature names when the model exposes contributions

The endpoint uses the trained ML3 Logistic Regression artifact loaded by ML5 at service startup. The React client continues to consume the original four response fields unchanged; the additional metadata fields are additive.
