# True Option Value Calculation Model (2025)

This project presents an interactive, web-based equity valuation model built in Python (Streamlit), designed to simulate complex startup exit scenarios. Unlike traditional calculators that rely solely on percentage ownership, this tool visualizes the impact of capital structure—specifically **Liquidation Preferences** and **Dilution**—on employee payout outcomes.

The model bridges the gap between theoretical offer letter numbers and actual realized value, serving as a dynamic tool for risk assessment under different market conditions (e.g., Standard vs. Distressed rounds).

### 📌 Model Objective

* **Visualize Risk Exposure:** Identify the "Zone of Zero" where common stock options are underwater due to investor liquidation preferences, even at non-zero exit valuations.
* **Analyze Waterfall Logic:** Simulate the hierarchical distribution of proceeds (Waterfall Analysis), prioritizing Preferred Stock repayment before Common Stock participation.
* **Assess Break-even Thresholds:** Calculate the precise exit valuation required for employees to realize a positive net profit after accounting for strike prices and investor hurdles.
* **Scenario Planning:** Compare payout outcomes under "Market Standard" terms (1x Non-Participating) versus "Distressed" terms (Multiple Liquidation Preferences).

### 🔑 Key Takeaways

* **Structure Over Percentage:** A specific ownership percentage (e.g., 0.1%) is meaningless without context; the Liquidation Preference creates a "hurdle" that must be cleared before ownership percentage applies.
* **The "Zone of Zero":** In downside scenarios with high liquidation multiples (e.g., 2x), employees may receive $0 payout even if the company sells for millions of dollars.
* **Dilution Impact:** Future financing rounds (Series B, C, D) significantly impact final payouts. The model demonstrates how a 20% dilution per round can reduce effective ownership despite a static share count.
* **Strike Price Sensitivity:** The model highlights how the exercise cost (Strike Price) acts as a secondary leverage point, further increasing the break-even valuation requirement.

### 🏗️ Model Structure

The application is built using a modular Python architecture:

* **Frontend (Streamlit):** Interactive sidebar for dynamic user inputs, including option grants, strike prices, and estimated future dilution.
* **Calculation Engine:** A dedicated backend class (`calculation_engine.py`) that processes the payment waterfall hierarchy, handling logic for:
    * Liquidation Preferences (1x, 2x, etc.)
    * Participation Rights (Participating vs. Non-Participating)
    * Common Stock Pro-rata Distribution
* **Visualization (Plotly):** Renders dynamic area charts to visualize the Net Profit profile across a range of simulated exit valuations.
* **Knowledge Base:** Integrated educational module explaining core VC concepts like the "Option Pool Shuffle" and "Liquidation Overhang."

### ⚙️ Key Assumptions (Base Methodology)

* **Waterfall Hierarchy:** The model assumes a standard priority stack where Preferred Stock investors are paid out fully before Common Stock shareholders.
* **Dilution Logic:** Uses a "Fully Diluted" approach where the user's effective ownership stake is adjusted based on a customizable dilution factor (0-80%) to simulate future fundraising.
* **Market Benchmarks:** Default scenarios are derived from aggregated VC market data (e.g., Fenwick & West surveys), simulating typical terms for Series A/B rounds.
* **Taxation:** All outputs are calculated on a **Pre-tax** basis (Gross Payout minus Exercise Cost).

### 🚫 Model Scope & Limitations

This model intentionally excludes:
* Complex multi-layered cap tables with varying seniority per share class (simplified to Aggregate Investors vs. Common).
* Tax implications such as AMT (Alternative Minimum Tax), NSO vs. ISO, or capital gains tax.
* Granular vesting schedule modeling (assumes fully vested or calculates based on total grant).
* This tool is designed for **educational and simulation purposes** only and does not constitute investment or legal advice.

### 📂 Files

* `app.py` – Main application script containing UI logic and visualization code.
* `calculation_engine.py` – Core mathematical logic for the waterfall distribution.
* `benchmarks.json` – Configuration file storing market standard and distressed term sheet parameters.
* `requirements.txt` – List of Python dependencies (Streamlit, Plotly, Pandas).

### 👤 Author

Built by **Guowei (Gary) Wu** as a portfolio project demonstrating Python financial modeling, SaaS equity analysis, and full-stack data application development.
