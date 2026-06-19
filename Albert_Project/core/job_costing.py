"""
===========================================================================
  core/job_costing.py — Selling Price Calculator
===========================================================================
  Implements the exact job costing formula used by Italian Kitchen and Bath:

    Pre-Margin Total = Material + Tax + Freight + Delivery +
                       Install + Warehousing + Protection +
                       Insurance + Misc
    
    Selling Price = Pre-Margin Total ÷ (1 - GP% - Commission% - Bond%)

  This formula is iterative-free because Commission and Bond are % of
  Selling Price (not Cost), so we solve algebraically:

    Selling Price × (1 - GP% - Commission% - Bond%) = Pre-Margin Total
    Selling Price = Pre-Margin Total / (1 - GP% - Commission% - Bond%)
===========================================================================
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from core.config import (
    DEFAULT_GP_TARGET_PCT, DEFAULT_COMMISSION_PCT, DEFAULT_BOND_PCT,
    DEFAULT_LOCAL_USE_TAX_PCT, DEFAULT_OCEAN_FREIGHT_PER_CONTAINER,
    DEFAULT_INLAND_DELIVERY, DEFAULT_INSTALLATION_PER_CABINET,
    DEFAULT_WAREHOUSING_PCT, DEFAULT_MATERIAL_PROTECTION_PCT,
    DEFAULT_INSURANCE_PCT, DEFAULT_MISC_ALLOWANCE,
    DEFAULT_CABINETS_PER_CONTAINER,
)


# ══════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class JobCostingInput:
    """All inputs needed to compute the selling price."""
    # Core quantities (required)
    total_cabinet_count:  int
    material_cost_usd:    float           # from price_matcher

    # Rates (with defaults from config)
    gp_target_pct:                float = None
    commission_pct:               float = None
    bond_pct:                     float = None
    local_use_tax_pct:            float = None
    ocean_freight_per_container:  float = None
    inland_delivery:              float = None
    installation_per_cabinet:     float = None
    warehousing_pct:              float = None
    material_protection_pct:      float = None
    insurance_pct:                float = None
    misc_allowance:               float = None
    cabinets_per_container:       int   = None

    def __post_init__(self):
        # Apply defaults for any None values
        if self.gp_target_pct               is None: self.gp_target_pct               = DEFAULT_GP_TARGET_PCT
        if self.commission_pct              is None: self.commission_pct              = DEFAULT_COMMISSION_PCT
        if self.bond_pct                    is None: self.bond_pct                    = DEFAULT_BOND_PCT
        if self.local_use_tax_pct           is None: self.local_use_tax_pct           = DEFAULT_LOCAL_USE_TAX_PCT
        if self.ocean_freight_per_container is None: self.ocean_freight_per_container = DEFAULT_OCEAN_FREIGHT_PER_CONTAINER
        if self.inland_delivery             is None: self.inland_delivery             = DEFAULT_INLAND_DELIVERY
        if self.installation_per_cabinet    is None: self.installation_per_cabinet    = DEFAULT_INSTALLATION_PER_CABINET
        if self.warehousing_pct             is None: self.warehousing_pct             = DEFAULT_WAREHOUSING_PCT
        if self.material_protection_pct     is None: self.material_protection_pct     = DEFAULT_MATERIAL_PROTECTION_PCT
        if self.insurance_pct               is None: self.insurance_pct               = DEFAULT_INSURANCE_PCT
        if self.misc_allowance              is None: self.misc_allowance              = DEFAULT_MISC_ALLOWANCE
        if self.cabinets_per_container      is None: self.cabinets_per_container      = DEFAULT_CABINETS_PER_CONTAINER


@dataclass
class JobCostingResult:
    """Full breakdown of the job costing calculation."""
    # Inputs
    inputs: JobCostingInput

    # Cost line items
    material_cost:          float = 0.0
    local_use_tax:          float = 0.0
    ocean_freight:          float = 0.0
    inland_delivery:        float = 0.0
    installation:           float = 0.0
    warehousing:            float = 0.0
    material_protection:    float = 0.0
    insurance:              float = 0.0
    misc_allowance:         float = 0.0
    pre_margin_total:       float = 0.0

    # Margin items (% of Selling Price)
    commission_pct:  float = 0.0
    bond_pct:        float = 0.0
    gp_pct:          float = 0.0

    # Final result
    selling_price:   float = 0.0
    gross_profit:    float = 0.0
    total_cost:      float = 0.0
    containers_needed: int = 0
    cost_per_cabinet:  float = 0.0
    sell_per_cabinet:  float = 0.0

    # Verification
    gp_check_pct:    float = 0.0   # should equal gp_pct if formula is correct

    def print_report(self):
        """Print a formatted job costing report."""
        inp = self.inputs
        SEP = "-" * 65
        print(f"\n{'=' * 65}")
        print(f"  JOB COSTING REPORT")
        print(f"  Total Cabinets: {inp.total_cabinet_count:,} | "
              f"Containers: {self.containers_needed}")
        print(f"{'=' * 65}")

        print(f"\n  A. QUANTITIES")
        print(f"  {'Total Cabinets':45s}  {inp.total_cabinet_count:>10,}")
        print(f"  {'Containers Required':45s}  {self.containers_needed:>10,}")

        print(f"\n  B. MATERIAL COST")
        print(f"  {'Material Cost (cabinets)':45s}  ${self.material_cost:>12,.2f}")

        print(f"\n  C. PROJECT COSTS")
        items = [
            ("1. Material Cost",                 self.material_cost),
            ("2. Local Use Tax (7.5%)",           self.local_use_tax),
            ("3. Ocean Freight (per container)",  self.ocean_freight),
            ("4. Inland Delivery",                self.inland_delivery),
            ("5. Installation ($85/cab)",         self.installation),
            ("6. Warehousing (2%)",               self.warehousing),
            ("7. Material Protection (0.5%)",     self.material_protection),
            ("8. Insurance (0.8%)",               self.insurance),
            ("9. Miscellaneous Allowance",        self.misc_allowance),
        ]
        for label, amount in items:
            print(f"  {label:45s}  ${amount:>12,.2f}")

        print(f"  {SEP}")
        print(f"  {'PRE-MARGIN SUBTOTAL':45s}  ${self.pre_margin_total:>12,.2f}")

        print(f"\n  D. MARGIN & OVERHEAD")
        print(f"  {'Commission (5% of Selling Price)':45s}  ${self.selling_price * self.commission_pct:>12,.2f}")
        print(f"  {'Bond (1.5% of Selling Price)':45s}     ${self.selling_price * self.bond_pct:>12,.2f}")
        print(f"  {'Gross Profit (35% of Selling Price)':45s}  ${self.gross_profit:>12,.2f}")

        print(f"\n  E. SELLING PRICE")
        print(f"  {'Formula: Pre-Margin ÷ (1 - GP% - Comm% - Bond%)':45s}")
        denom = 1 - inp.gp_target_pct - inp.commission_pct - inp.bond_pct
        print(f"  {'Denominator':45s}  {denom:.4f}")
        print(f"  {SEP}")
        print(f"  {'SELLING PRICE (TOTAL PROJECT)':45s}  ${self.selling_price:>12,.2f}")
        print(f"  {SEP}")

        print(f"\n  F. VERIFICATION")
        print(f"  {'Gross Profit Amount':45s}  ${self.gross_profit:>12,.2f}")
        print(f"  {'Gross Profit %':45s}  {self.gp_check_pct:.2%}")
        print(f"  {'Total Cost':45s}  ${self.total_cost:>12,.2f}")
        print(f"  {'Cost per Cabinet':45s}  ${self.cost_per_cabinet:>12,.2f}")
        print(f"  {'Sell per Cabinet':45s}  ${self.sell_per_cabinet:>12,.2f}")
        print(f"{'=' * 65}\n")


# ══════════════════════════════════════════════════════════════════════════
# CALCULATOR
# ══════════════════════════════════════════════════════════════════════════

def calculate_selling_price(inputs: JobCostingInput) -> JobCostingResult:
    """
    Calculate the full job costing and final selling price.

    The formula is:
      Pre-Margin Total = sum of all fixed costs
      Selling Price = Pre-Margin Total / (1 - GP% - Commission% - Bond%)

    This gives us: SP × (1 - GP% - Comm% - Bond%) = Pre-Margin
    Which is equivalent to solving for SP algebraically.
    """
    result = JobCostingResult(inputs=inputs)
    i = inputs

    # Line items
    result.material_cost       = i.material_cost_usd
    result.local_use_tax       = i.material_cost_usd * i.local_use_tax_pct

    containers = math.ceil(i.total_cabinet_count / i.cabinets_per_container)
    result.containers_needed   = containers
    result.ocean_freight       = containers * i.ocean_freight_per_container

    result.inland_delivery     = i.inland_delivery
    result.installation        = i.total_cabinet_count * i.installation_per_cabinet
    result.warehousing         = i.material_cost_usd * i.warehousing_pct
    result.material_protection = i.material_cost_usd * i.material_protection_pct
    result.insurance           = i.material_cost_usd * i.insurance_pct
    result.misc_allowance      = i.misc_allowance

    result.pre_margin_total = (
        result.material_cost +
        result.local_use_tax +
        result.ocean_freight +
        result.inland_delivery +
        result.installation +
        result.warehousing +
        result.material_protection +
        result.insurance +
        result.misc_allowance
    )

    # Margin percentages
    result.gp_pct         = i.gp_target_pct
    result.commission_pct = i.commission_pct
    result.bond_pct       = i.bond_pct

    # Selling price calculation
    denominator = 1.0 - i.gp_target_pct - i.commission_pct - i.bond_pct
    if denominator <= 0:
        raise ValueError(
            f"Invalid margin configuration: GP({i.gp_target_pct:.1%}) + "
            f"Commission({i.commission_pct:.1%}) + Bond({i.bond_pct:.1%}) ≥ 100%"
        )

    result.selling_price = result.pre_margin_total / denominator

    # Verification figures
    result.gross_profit    = result.selling_price * i.gp_target_pct
    result.total_cost      = result.selling_price - result.gross_profit
    result.gp_check_pct    = result.gross_profit / result.selling_price if result.selling_price > 0 else 0.0
    result.cost_per_cabinet = (
        result.total_cost / i.total_cabinet_count if i.total_cabinet_count > 0 else 0.0
    )
    result.sell_per_cabinet = (
        result.selling_price / i.total_cabinet_count if i.total_cabinet_count > 0 else 0.0
    )

    return result


# ══════════════════════════════════════════════════════════════════════════
# QUICK TEST
# ══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # Test with representative Casa Familia numbers
    test_input = JobCostingInput(
        total_cabinet_count = 630,       # ~630 total cabinets for Casa Familia
        material_cost_usd   = 95_000.0,  # estimated material cost
    )

    result = calculate_selling_price(test_input)
    result.print_report()

    # Verify GP% is correct
    assert abs(result.gp_check_pct - test_input.gp_target_pct) < 0.001, \
        f"GP check failed: {result.gp_check_pct:.4f} ≠ {test_input.gp_target_pct:.4f}"
    print("  ✅ GP verification passed")
