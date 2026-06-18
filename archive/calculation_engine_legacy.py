import pandas as pd

class ShareClass:
    """
    Defines the terms for a specific funding round (e.g., Series A).
    """
    def __init__(self, name, investment_amount, liquidation_pref, is_participating, conversion_ratio=1.0):
        self.name = name
        self.investment_amount = investment_amount  # Capital invested (e.g., $10M)
        self.liquidation_pref = liquidation_pref    # Liquidation preference multiple (e.g., 1.0x or 2.0x)
        self.is_participating = is_participating    # Participation rights (True/False)
        self.conversion_ratio = conversion_ratio    # Conversion ratio to common stock (usually 1.0)

class UserEquity:
    """
    Defines the user's specific equity/option details.
    """
    def __init__(self, total_shares, strike_price):
        self.total_shares = total_shares  # Number of options/shares held
        self.strike_price = strike_price  # Strike price per share

def calculate_payout(exit_valuation, share_classes, total_company_shares, user_equity):
    """
    Core Calculation Engine:
    Inputs:
        - exit_valuation: Total value the company is sold for
        - share_classes: List of preferred stock rounds (ShareClass objects)
        - total_company_shares: Fully diluted share count
        - user_equity: UserEquity object containing user's specifics
    
    Returns:
        - net_profit: The actual cash value the user takes home (pre-tax)
    """
    
    remaining_cash = exit_valuation
    
    # --- Step 1: Liquidation Preference (The Waterfall) ---
    # Investors get paid their guaranteed return first.
    print(f"--- Starting Calculation: Exit Valuation ${exit_valuation:,.0f} ---")
    
    for share in share_classes:
        # Preference Amount = Investment * Multiple
        pref_amount = share.investment_amount * share.liquidation_pref
        
        # Actual Payout = Min(Remaining Cash, Preference Amount)
        payout = min(remaining_cash, pref_amount)
        
        remaining_cash -= payout
        print(f"Paid to {share.name}: ${payout:,.0f} (Remaining Cash: ${remaining_cash:,.0f})")
    
    # --- Step 2: Common Stock Distribution ---
    # Simplified Model: Assuming Non-Participating Preferred for MVP.
    # Any remaining cash is distributed pro-rata to common shareholders.
    
    if remaining_cash > 0:
        price_per_share = remaining_cash / total_company_shares
        
        # Gross value of your holdings
        your_gross_value = user_equity.total_shares * price_per_share
        
        # Deduct cost to exercise (Strike Price * Shares)
        exercise_cost = user_equity.total_shares * user_equity.strike_price
        
        # Net Profit (Cannot be negative)
        net_profit = max(0, your_gross_value - exercise_cost)
        
        print(f"Implied Share Price: ${price_per_share:.2f}")
        print(f"Your Gross Value: ${your_gross_value:,.2f}")
        print(f"Your Net Profit: ${net_profit:,.2f}")
        return net_profit
    else:
        print("Funds exhausted during liquidation preference. Common stock value is $0.")
        return 0
    

# --- Test Script (Executes only when running this file directly) ---
if __name__ == "__main__":
    # Scenario Setup:
    # Company raised Series A: $10M at 1x Non-Participating
    series_a = ShareClass(name="Series A", investment_amount=10000000, liquidation_pref=1.0, is_participating=False)
    
    # Your Offer: 10,000 shares, Strike Price $1.0, Total Shares 10M (0.1% ownership)
    my_equity = UserEquity(total_shares=10000, strike_price=1.0)
    company_total_shares = 10000000
    
    # Test 1: Downside Scenario (Exit < Invested Capital)
    print("\n[Case 1: Downside Scenario]")
    calculate_payout(5000000, [series_a], company_total_shares, my_equity)
    
    # Test 2: Break-even Scenario (Exit = Invested Capital)
    print("\n[Case 2: Break-even Scenario]")
    calculate_payout(10000000, [series_a], company_total_shares, my_equity)
    
    # Test 3: Upside Scenario (Exit = 10x Invested Capital)
    print("\n[Case 3: Upside Scenario]")
    calculate_payout(100000000, [series_a], company_total_shares, my_equity)