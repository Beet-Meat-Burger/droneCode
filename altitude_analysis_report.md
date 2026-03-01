# Drone Failure Risk Assessment: Altitude Impact Analysis

**Report Generated:** 2026-03-01 18:45:42

## Executive Summary

This analysis quantifies the relationship between drone failure altitude and casualty probability.
Key finding: **Casualty risk is NOT monotonic with altitude** — it depends on the balance between
terminal velocity (kinetic energy) and population density at impact locations.

---

## Methodology

### 1. Physics Model

#### Terminal Velocity Calculation
Terminal velocity is calculated using the standard aerodynamic formula:

$$v_{terminal} = \sqrt{\frac{2mg}{\rho A C_d}}$$

Where:
- **m** = drone mass = 6.3 kg (DJI Matrice 300 RTK)
- **g** = gravitational acceleration = 9.81 m/s²
- **ρ** = air density = 1.225 kg/m³ (sea level, standard atmosphere)
- **A** = reference area = 0.08 m² (drone cross-section)
- **Cd** = drag coefficient = 0.47 (sphere/cylinder approximation)

Air density decreases with altitude following:
$$\rho(h) = \rho_0 \cdot e^{-h/8500}$$

#### Kinetic Energy at Impact
$$E_k = \frac{1}{2}mv^2$$

Terminal velocity increases with altitude (less air resistance). Higher altitudes → higher velocity at impact → higher kinetic energy.

### 2. Casualty Model

#### Death Probability (velocity-dependent)

Death probability is calculated based on kinetic energy, NOT altitude:

- **KE < 500J:** 5% death probability (survivable impact)
- **500J ≤ KE < 1000J:** Linear ramp from 5% to 50%
- **KE ≥ 1000J:** Linear ramp from 50% to 95%, capped at 95%

This model is based on blunt force trauma thresholds for humans.

#### Impact Probability (population-dependent)

Impact probability depends on whether a person is in the 1m² impact zone:

$$P({hit}) = \min(1.0, \rho_{	ext{people}}/10000)$$

Where ρ_people = population density from WorldPop HK dataset (people per 100m × 100m cell)

#### Casualty Probability

$$P({casualty}) = P({hit}) \times P({death})$$

Binary outcome per simulation: **0 or 1 casualty** (realistic for drone impact)

### 3. Simulation Parameters

- **Test Locations:** Multiple sampled points on optimized drone path (random iterations)
- **Altitude Range:** 50 ft to 1000 ft (50 ft increments = 20 bands)
- **Location Iterations:** 10 different random locations per altitude
- **Simulations per Location:** 100
- **Total Monte Carlo Runs:** 200000 simulations
- **Drone Model:** DJI Matrice 300 RTK (6.3 kg empty weight)
- **Population Data:** WorldPop HK 2020 (100m resolution)

### 4. Wind Drift Modeling

During descent, horizontal drift is applied based on wind:

$$d_{drift} = v_{wind} \times t_{descent}$$

Wind direction is uniformly random (0-360°). This adds variability to impact location but doesn't affect terminal velocity or kinetic energy.

---

## Key Physics Insights

1. **Terminal Velocity Increases with Altitude**
   - Lower altitude = slower impact
   - Higher altitude = faster impact (but not dramatically — air resistance is large)
   - Typical range: 14.7 m/s to 40.6 m/s

2. **Kinetic Energy Scales with Altitude**
   - Minimum KE: ~681 J (at 50 ft)
   - Maximum KE: ~5184 J (at 1000 ft)

3. **Death Probability Depends on Impact Energy**
   - Below ~500J: Low death probability (~5%)
   - Above ~1000J: High death probability (~50-95%)
   - Current altitudes are mostly in the 50-90% range

---

## Results

### Summary Statistics by Altitude

| Altitude (ft) | Velocity (m/s) | Kinetic Energy (J) | Death Probability | Casualty Probability |
|---|---|---|---|---|
| 50 | 14.70 | 681.1 | 21.3% | 1.390% |
| 100 | 19.50 | 1197.8 | 51.8% | 3.310% |
| 150 | 22.76 | 1631.9 | 55.7% | 3.110% |
| 200 | 25.26 | 2009.6 | 59.1% | 3.390% |
| 250 | 27.28 | 2345.0 | 62.1% | 3.840% |
| 300 | 28.99 | 2647.0 | 64.8% | 3.950% |
| 350 | 30.46 | 2921.8 | 67.3% | 3.220% |
| 400 | 31.74 | 3173.6 | 69.6% | 3.760% |
| 450 | 32.88 | 3406.1 | 71.7% | 4.370% |
| 500 | 33.91 | 3621.7 | 73.6% | 3.440% |
| 550 | 34.84 | 3822.7 | 75.4% | 4.020% |
| 600 | 35.68 | 4010.7 | 77.1% | 4.570% |
| 650 | 36.46 | 4187.3 | 78.7% | 4.280% |
| 700 | 37.18 | 4353.6 | 80.2% | 4.400% |
| 750 | 37.84 | 4510.6 | 81.6% | 4.620% |
| 800 | 38.46 | 4659.3 | 82.9% | 4.780% |
| 850 | 39.04 | 4800.4 | 84.2% | 4.930% |
| 900 | 39.58 | 4934.5 | 85.4% | 5.380% |
| 950 | 40.09 | 5062.4 | 86.6% | 5.360% |
| 1000 | 40.57 | 5184.3 | 87.7% | 4.600% |

### Interpretation

**Casualty Probability** = P(person in impact zone) × P(death | hit)

- Ranges from 1.390% to 5.380%
- These are **per-impact** probabilities, **not cumulative**
- Over 100 simulations per altitude, expect roughly 0-1 casualties at most altitudes due to low population density along routes

---

## Limitations & Assumptions

1. **Impact Area:** Fixed at 1m² (drone cross-section). Actual debris spread not modeled.
2. **Population Density:** Static WorldPop data (2020). Doesn't account for temporal variation.
3. **Wind Drift:** Simple model. Actual aerodynamics are more complex.
4. **Single Drone Type:** Analysis uses DJI Matrice 300 RTK specs. Results vary by drone mass/size.
5. **Geographic Scope:** Hong Kong only.
6. **Death Threshold:** 1000J assumption based on literature; actual thresholds vary by impact angle, body part, etc.

---

## Recommendations

1. **Risk Mitigation:** Most risk occurs at altitudes > 200 ft where KE > 1000J
2. **Route Planning:** Avoid high-population areas during high-altitude operations
3. **Redundancy:** Consider parachute/failsafe systems for operations > 300 ft
4. **Validation:** Cross-check death probability model with biomechanics literature

---

## Files Generated

- `altitude_analysis.csv` - Raw simulation data (200000 rows)
- `altitude_summary.csv` - Aggregated statistics (20 altitude bands)
- `altitude_plot.png` - Visualization (4-panel chart)
- `altitude_analysis_report.md` - This report

