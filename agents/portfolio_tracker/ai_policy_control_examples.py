"""
AI Agent Policy Control - Usage Examples (Four-Tier Framework v3.0)
====================================================================

This script demonstrates how an AI agent can control the risk tolerance policy
dynamically based on market conditions, portfolio performance, or other signals.

Four-Tier Risk Framework:
- HIGH: Opportunistic expansion (VIX <15, DD <8%) - 5-10% of time
- MODERATE-AGGRESSIVE: Default growth-focused (VIX 15-20) - 65-70% of time
- MODERATE: Defensive buffer (VIX 20-25) - 10-15% of time
- LOW: Crisis survival (VIX >25) - 10-15% of time
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from risk_override import RiskPolicyValidator, PolicyManager, RiskProfile
import json


def example_1_check_current_policy():
    """Example 1: Check which policy is currently active"""
    print("\n" + "="*70)
    print("EXAMPLE 1: Check Active Policy")
    print("="*70)
    
    validator = RiskPolicyValidator()
    current_policy = validator.get_current_policy()
    
    print(f"\nActive Policy: {current_policy['profile']}")
    print(f"Max Drawdown: {current_policy['max_drawdown']}%")
    print(f"Circuit Breaker: {current_policy['circuit_breaker']}%")
    print(f"Max Leverage: {current_policy['max_leverage']}x")
    print(f"Single Position Max: {current_policy['single_position_max']}%")


def example_2_switch_to_conservative():
    """Example 2: AI agent switches to LOW (conservative) policy due to high VIX"""
    print("\n" + "="*70)
    print("EXAMPLE 2: AI Agent Switches to Conservative Policy (Crisis Mode)")
    print("="*70)

    validator = RiskPolicyValidator()
    vix_level = validator.get_vix_level()

    print(f"\nCurrent VIX: {vix_level:.2f}")
    print(f"Current Policy: {validator.policy_profile.value}")

    # AI decision logic: VIX > 25 triggers crisis mode (LOW policy)
    if vix_level > 25:
        print("🚨 CRISIS VOLATILITY DETECTED (VIX > 25)")
        print("AI Decision: Switch to LOW (Capital Preservation) policy")

        validator.switch_policy(
            RiskProfile.LOW,
            reason=f"VIX spiked to {vix_level:.2f} (>25), switching to capital preservation mode"
        )

        print("\n✅ Policy switched to LOW (30/70 preservation priority)")
        print(f"   - Max Drawdown: {validator.config.max_drawdown}%")
        print(f"   - Single Position: {validator.config.single_position_max}%")
        print(f"   - Max Leverage: {validator.config.max_leverage}x")

    elif vix_level > 20:
        print("⚠️  ELEVATED VOLATILITY DETECTED (VIX 20-25)")
        print("AI Decision: Switch to MODERATE (Defensive Buffer) policy")

        validator.switch_policy(
            RiskProfile.MODERATE,
            reason=f"VIX elevated to {vix_level:.2f} (20-25), switching to defensive buffer"
        )

        print("\n✅ Policy switched to MODERATE (60/40 defensive buffer)")
        print(f"   - Max Drawdown: {validator.config.max_drawdown}%")
        print(f"   - Single Position: {validator.config.single_position_max}%")
        print(f"   - Max Leverage: {validator.config.max_leverage}x")

    else:
        print("✓ VIX within normal range (15-20), maintaining MODERATE-AGGRESSIVE default")


def example_3_switch_to_aggressive():
    """Example 3: AI agent switches to HIGH (opportunistic) after exceptional conditions"""
    print("\n" + "="*70)
    print("EXAMPLE 3: AI Agent Switches to Opportunistic HIGH Policy")
    print("="*70)

    validator = RiskPolicyValidator()
    vix_level = validator.get_vix_level()
    drawdown = validator.health_monitor.calculate_drawdown()

    print(f"\nCurrent VIX: {vix_level:.2f}")
    print(f"Current Drawdown: {drawdown:.2f}%")
    print(f"Current Policy: {validator.policy_profile.value}")

    # AI decision logic: VIX < 15 + Low drawdown = exceptional conditions for HIGH
    if vix_level < 15 and drawdown < 8:
        print("✅ EXCEPTIONAL CONDITIONS DETECTED")
        print("   - Very low volatility (VIX < 15)")
        print("   - Portfolio healthy (drawdown < 8%)")
        print("AI Decision: Scale UP to HIGH (Opportunistic Growth) policy")

        validator.switch_policy(
            RiskProfile.HIGH,
            reason=f"Exceptional market: VIX={vix_level:.2f}, DD={drawdown:.2f}%. Opportunistic expansion."
        )

        print("\n✅ Policy switched to HIGH (80/20 opportunistic growth)")
        print(f"   - Max Drawdown: {validator.config.max_drawdown}%")
        print(f"   - Single Position: {validator.config.single_position_max}%")
        print(f"   - Max Leverage: {validator.config.max_leverage}x")
        print("\n📌 Note: Return to MODERATE-AGGRESSIVE when VIX > 15 or drawdown > 8%")
    else:
        print("⚠️  Conditions not optimal for HIGH policy")
        print("   Staying in MODERATE-AGGRESSIVE (default growth-focused mode)")


def example_4_drawdown_driven_switch():
    """Example 4: AI agent switches policy based on drawdown (Four-Tier Framework)"""
    print("\n" + "="*70)
    print("EXAMPLE 4: Drawdown-Driven Policy Switch (Four-Tier)")
    print("="*70)

    validator = RiskPolicyValidator()
    drawdown = validator.health_monitor.calculate_drawdown()

    print(f"\nCurrent Drawdown: {drawdown:.2f}%")
    print(f"Current Policy: {validator.policy_profile.value}")

    # AI decision logic: Four-tier drawdown thresholds
    if drawdown > 15:
        print("\n🚨 Critical drawdown detected")
        print("AI Decision: Capital preservation - switch to LOW")
        validator.switch_policy(
            RiskProfile.LOW,
            reason=f"Drawdown {drawdown:.2f}% exceeds 15% threshold"
        )
        print("✅ Switched to LOW (30/70 preservation)")

    elif drawdown > 10 and validator.policy_profile in [RiskProfile.HIGH, RiskProfile.MODERATE_AGGRESSIVE]:
        print("\n⚠️  Elevated drawdown detected")
        print("AI Decision: Defensive buffer - switch to MODERATE")
        validator.switch_policy(
            RiskProfile.MODERATE,
            reason=f"Drawdown {drawdown:.2f}% exceeds 10% threshold"
        )
        print("✅ Switched to MODERATE (60/40 defensive buffer)")

    elif drawdown > 8 and validator.policy_profile == RiskProfile.HIGH:
        print("\n⚠️  Drawdown approaching limit for HIGH policy")
        print("AI Decision: Return to default - switch to MODERATE-AGGRESSIVE")
        validator.switch_policy(
            RiskProfile.MODERATE_AGGRESSIVE,
            reason=f"Drawdown {drawdown:.2f}% exceeds 8% HIGH policy limit"
        )
        print("✅ Switched to MODERATE-AGGRESSIVE (65/35 default)")

    elif drawdown < 5 and validator.policy_profile == RiskProfile.MODERATE:
        print("\n✅ Portfolio recovered, conditions favorable")
        print("AI Decision: Return to default - switch to MODERATE-AGGRESSIVE")
        validator.switch_policy(
            RiskProfile.MODERATE_AGGRESSIVE,
            reason=f"Recovery confirmed: drawdown {drawdown:.2f}%"
        )
        print("✅ Switched to MODERATE-AGGRESSIVE (65/35 default)")

    else:
        print(f"✓ Drawdown {drawdown:.2f}% acceptable for {validator.policy_profile.value} policy")


def example_5_market_regime_detection():
    """Example 5: AI agent switches based on comprehensive market regime analysis (Four-Tier)"""
    print("\n" + "="*70)
    print("EXAMPLE 5: Market Regime Detection & Policy Adjustment (Four-Tier)")
    print("="*70)

    validator = RiskPolicyValidator()

    # Collect market signals
    vix_level = validator.get_vix_level()
    drawdown = validator.health_monitor.calculate_drawdown()
    portfolio_health = validator.health_monitor.get_portfolio_health()

    print(f"\nMarket Signals:")
    print(f"  VIX: {vix_level:.2f}")
    print(f"  Drawdown: {drawdown:.2f}%")
    print(f"  Portfolio Value: ${portfolio_health['portfolio_value']:,.2f}")

    # AI regime classification (Four-Tier Framework)
    if vix_level < 15 and drawdown < 8:
        regime = "EXCEPTIONAL"
        recommended_policy = RiskProfile.HIGH
        confidence = 0.85
    elif vix_level > 25 or drawdown > 15:
        regime = "CRISIS"
        recommended_policy = RiskProfile.LOW
        confidence = 0.90
    elif vix_level > 20 or drawdown > 10:
        regime = "ELEVATED"
        recommended_policy = RiskProfile.MODERATE
        confidence = 0.80
    else:
        # Default: VIX 15-20 and drawdown < 10%
        regime = "NORMAL_GROWTH"
        recommended_policy = RiskProfile.MODERATE_AGGRESSIVE
        confidence = 0.85

    print(f"\nAI Regime Detection (Four-Tier):")
    print(f"  Regime: {regime}")
    print(f"  Recommended Policy: {recommended_policy.value}")
    print(f"  Confidence: {confidence:.0%}")

    if validator.policy_profile != recommended_policy:
        print(f"\n🔄 Switching from {validator.policy_profile.value} to {recommended_policy.value}")

        validator.switch_policy(
            recommended_policy,
            reason=f"Market regime: {regime} (confidence: {confidence:.0%})"
        )
        print("✅ Policy adjusted to match market conditions")
    else:
        print(f"\n✓ Current policy {validator.policy_profile.value} matches market regime")


def example_6_view_policy_history():
    """Example 6: View policy switch history"""
    print("\n" + "="*70)
    print("EXAMPLE 6: View Policy History")
    print("="*70)
    
    config_file = PolicyManager.CONFIG_FILE
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            data = json.load(f)
        
        print(f"\nActive Policy: {data.get('active_policy')}")
        print(f"Last Changed: {data.get('changed_at')}")
        print(f"Reason: {data.get('reason', 'N/A')}")
    else:
        print("\n⚠️  No policy history file found (default: MODERATE)")


def main():
    """Run all examples"""
    print("\n" + "="*70)
    print("AI AGENT POLICY CONTROL - DEMONSTRATION")
    print("="*70)
    
    try:
        example_1_check_current_policy()
        example_2_switch_to_conservative()
        example_3_switch_to_aggressive()
        example_4_drawdown_driven_switch()
        example_5_market_regime_detection()
        example_6_view_policy_history()
        
        print("\n" + "="*70)
        print("DEMONSTRATION COMPLETE")
        print("="*70)
        print("\nFour-Tier Risk Framework (v3.0):")
        print("  HIGH              - Opportunistic expansion (VIX <15)")
        print("  MODERATE-AGGRESSIVE - Default growth-focused (VIX 15-20)")
        print("  MODERATE          - Defensive buffer (VIX 20-25)")
        print("  LOW               - Crisis survival (VIX >25)")
        print("\nAI agents use these patterns to dynamically adjust risk policies")
        print("based on market conditions, portfolio performance, and risk signals.")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
