# Data Science & Machine Learning Specification
## In-Play Win Probability & Match Intelligence Model
### Godrej Cricket Intelligence — Real-Time Cricket Analytics

This document details the Machine Learning architecture, feature engineering pipeline, domain boundary constraints, and evaluation metrics for the **In-Play Cricket Win Probability Model** implemented in `src/ml_win_probability.py` and `src/train_ml_model.py`.

---

## 1. Problem Formulation & Data Science Objective

In limited-overs T20 cricket (e.g. IPL), estimating the **in-play victory probability** of the chasing team at any discrete delivery state $t$:

$$P(\text{Win} = 1 \mid \mathcal{S}_t)$$

where the state $\mathcal{S}_t = \langle R_t, W_t, B_t, T \rangle$ consists of:
* $R_t$: Cumulative runs scored by the chasing team at delivery $t$.
* $W_t$: Wickets lost by the chasing team ($0 \le W_t \le 10$).
* $B_t$: Legal deliveries bowled ($0 \le B_t \le 120$).
* $T$: Target runs set by the team batting first.

---

## 2. Domain Boundary Invariants (Physical Constraints)

Unlike generic classification tasks, cricket outcomes are constrained by deterministic physical rules:

1. **Target Attainment Invariant:**
   $$\forall t, \quad R_t \ge T \implies P(\text{Win} = 1) = 1.0 \quad (100.0\%)$$
2. **All-Out Invariant:**
   $$\forall t, \quad W_t \ge 10 \land R_t < T \implies P(\text{Win} = 1) = 0.0 \quad (0.0\%)$$
3. **Delivery Exhaustion Invariant:**
   $$\forall t, \quad B_t \ge 120 \land R_t < T \implies P(\text{Win} = 1) = 0.0 \quad (0.0\%)$$

Any unconstrained neural network or tree model may predict $P(\text{Win}) = 0.94$ when a team has lost 10 wickets if it is close to the score. Our architecture wraps the statistical estimator with an **Invariant Guard Layer** enforcing strict boundary compliance.

---

## 3. Feature Engineering Pipeline

The model transforms raw state variables into 9 statistically correlated features:

| Feature Name | Mathematical Definition | Domain Significance |
| :--- | :--- | :--- |
| **`runs_needed`** | $\max(0, T - R_t)$ | Absolute deficit remaining. |
| **`balls_remaining`** | $\max(0, 120 - B_t)$ | Deliveries remaining to score deficit. |
| **`wickets_in_hand`** | $\max(0, 10 - W_t)$ | Available batting resources. |
| **`required_run_rate`** | $\left(\frac{\text{runs\_needed}}{\text{balls\_remaining}}\right) \times 6$ | Scoring pace required per 6-ball over. |
| **`current_run_rate`** | $\left(\frac{R_t}{B_t}\right) \times 6$ | Demonstrated scoring momentum. |
| **`run_rate_diff`** | $\text{RRR} - \text{CRR}$ | Pace acceleration gap. |
| **`pressure_index`** | $\frac{\text{RRR}}{\text{wickets\_in\_hand} + 1}$ | Non-linear interaction between target difficulty and resource scarcity. |
| **`is_powerplay`** | $\mathbb{I}(B_t \le 36)$ | Field restriction regime (2 fielders outside 30-yard circle). |
| **`is_death`** | $\mathbb{I}(B_t \ge 96)$ | High-risk death overs phase. |

---

## 4. Model Architecture & Statistical Calibration

We deploy an **$L_2$-penalized Logistic Regression** model calibrated on a transition corpus of 6,000 T20 match states.

$$\text{logit}(P) = \beta_0 + \sum_{j=1}^{9} \beta_j X_j$$

$$P(\text{Win} = 1) = \frac{1}{1 + e^{-\text{logit}(P)}}$$

### Why Logistic Regression over Complex Black-Box Ensembles?
1. **Calibrated Probabilities:** Logistic regression directly optimizes Bernoulli log-likelihood, producing true probabilities rather than uncalibrated scores.
2. **Sub-millisecond Inference:** Directly foldable into high-frequency streaming loops (<0.05 ms per prediction).
3. **Interpretability:** Feature coefficients represent log-odds, allowing coaches and analysts to audit model weights.

---

## 5. Model Evaluation Metrics (Hold-out Test Set)

The model was trained on 4,500 match states and evaluated on a holdout test set of 1,500 states:

| Metric | Holdout Score | Industry Benchmark | Verdict |
| :--- | :---: | :---: | :---: |
| **Classification Accuracy** | **89.00%** | $> 80.0\%$ | **Superior** |
| **ROC-AUC Score** | **0.9557** | $> 0.8500$ | **Exceptional** |
| **Brier Calibration Score** | **0.0766** | $< 0.1500$ | **Highly Calibrated** |
| **Log Loss** | **0.2525** | $< 0.4000$ | **Optimal Convergence** |
| **5-Fold Cross-Val ROC-AUC** | **0.9548 $\pm$ 0.0046** | $> 0.8500$ | **High Generalization** |

### Feature Coefficients (Log-Odds Impact):
* **`+ wickets_in_hand (+0.5632)`**: Largest positive driver of chase success.
* **`+ is_powerplay (+0.4531)`**: Favorable field restrictions elevate win probability.
* **`- pressure_index (-0.5169)`**: High required rate combined with low wickets rapidly destroys win odds.
* **`- is_death (-0.3865)`**: Late-innings pressure heavily favors the fielding team.
* **`- required_run_rate (-0.2812)`**: Demanding scoring rate reduces win expectancy.

---

## 6. How to Run & Reproduce

### 1. In-Play CLI Prediction:
```bash
python src/main.py predict-win-prob --runs 99 --wickets 3 --overs 6.6 --target 215 --batting "Chennai Super Kings" --bowling "Gujarat Titans"
```

### 2. Retrain & Calibrate:
```bash
python src/main.py train-ml
```

### 3. Automated Test Suite:
```bash
pytest tests/test_ml_win_probability.py -v
```

### 4. Interactive Jupyter Notebook:
Open [`notebooks/01_inplay_win_probability_modeling.ipynb`](file:///d:/Godrej_RealTime_Dashboard/notebooks/01_inplay_win_probability_modeling.ipynb) to inspect interactive scenario evaluations.
