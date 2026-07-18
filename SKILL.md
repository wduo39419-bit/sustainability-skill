---
name: sustainability-skill
description: Evidence-based assessment of a scientific or industrial technology across carbon emissions and green-economy value, real profitability, and deployment feasibility. Use for technology screening, R&D prioritization, pilot approval, commercialization reviews, investment memos, sustainability claims, and go/no-go decisions.
---

# Sustainability Skill

## Purpose

Evaluate whether a technology has practical value by combining environmental performance, economic returns, and implementation feasibility. Produce a decision-ready assessment that distinguishes verified evidence, user-provided data, assumptions, and unresolved risks.

Do not treat the result as a precise investment recommendation when critical inputs are missing. Use scenarios, sensitivity analysis, confidence levels, and explicit validation milestones.

## Operating principles

- Define the application, scale, geography, time horizon, and comparison baseline before scoring.
- Compare like with like: specify the functional unit, system boundary, capacity, utilization, lifetime, and denominator for every metric.
- Separate absolute performance from improvement relative to the incumbent or best available alternative.
- Never invent technical, financial, regulatory, or emissions data. Mark estimates and request high-impact missing inputs.
- Use conservative assumptions for early-stage technologies and state when subsidies, carbon prices, or credits are required for viability.
- Use a composite score only as a summary. Preserve dimension-level results and apply veto conditions for fatal safety, regulatory, supply, or scale-up barriers.
- Report uncertainty and the evidence needed to change the decision.

## Workflow

### 1. Frame the technology

Extract or ask for: technology description, use case, customer, output, capacity, maturity stage, location, deployment date, baseline alternative, available data, and decision question.

If the baseline or functional unit is unclear, resolve that before calculating benefits. For screening, proceed with clearly labeled assumptions and identify the decision-critical unknowns.

### 2. Assess green value and carbon

Quantify, where data permit:

- lifecycle greenhouse-gas emissions in kg CO2e per functional unit;
- absolute emissions and emissions avoided versus the baseline;
- energy, water, land, critical-material, and waste intensity;
- upstream, operational, transport, and end-of-life contributions;
- pollution-transfer risks and circularity/resource-recovery benefits;
- abatement cost per tCO2e avoided;
- dependence on renewable electricity, offsets, subsidies, carbon pricing, or certificates.

State the system boundary and whether results are attributional or consequential. Flag rebound effects, double counting of avoided emissions, uncertain end-of-life assumptions, and claims based only on offsets.

### 3. Assess actual profitability

Build a transparent unit-economics and cash-flow view covering:

- revenue, price, volume, utilization, and ramp-up;
- CAPEX, replacement CAPEX, fixed OPEX, variable OPEX, energy, labor, maintenance, logistics, and compliance costs;
- gross margin, operating margin, break-even volume and price;
- payback period, NPV, IRR, and cumulative cash flow when inputs support them;
- working-capital needs and financing or scale-up constraints;
- sensitivity to price, energy, feedstock, yield, utilization, carbon price, subsidy, CAPEX, and discount rate.

Use conservative, base, and optimistic cases. Show which cases remain viable without policy support. For early-stage technologies, use ranges rather than false precision.

### 4. Assess deployment feasibility

Evaluate:

- technology maturity and independent validation;
- continuous operation, yield, reliability, quality, and scale-up evidence;
- feedstock, equipment, utilities, suppliers, and serviceability;
- compatibility with existing facilities and required infrastructure;
- construction lead time, operating skills, safety, environmental permits, and standards;
- intellectual-property freedom to operate and critical licensing dependencies;
- customer adoption, procurement cycle, switching cost, and offtake evidence;
- organizational capability and pilot-to-commercial transition plan.

Classify barriers as technical, economic, supply-chain, regulatory, market, organizational, or social. Mark fatal blockers separately from manageable risks.

### 5. Synthesize the decision

Score each dimension on a 0–5 scale only after the evidence review:

- 0: infeasible or materially negative;
- 1: weak, unverified, or economically unattractive;
- 2: plausible but major gaps remain;
- 3: conditionally viable;
- 4: strong evidence and attractive performance;
- 5: independently validated, commercially robust, and clearly superior to the baseline.

Report dimension scores, not just a total. Use the default interpretation:

- **Recommend**: no fatal blockers, all dimensions ≥3, and the base case is viable;
- **Conditionally recommend**: promising but one or more decision-critical assumptions require a bounded pilot or commercial validation;
- **Continue validation**: evidence or economics are insufficient for a deployment decision;
- **Do not recommend now**: fatal blocker or base case fails with no credible mitigation.

Calculate a weighted summary only when the user provides priorities. Otherwise use equal weights as a transparent screening aid and state that it is not a universal value judgment.

## Required output

Structure the response as:

1. Executive conclusion and decision category.
2. Technology, use case, baseline, boundary, and key assumptions.
3. Green-economy and carbon assessment.
4. Profitability and scenario economics.
5. Deployment-feasibility assessment.
6. Scorecard with dimension scores, confidence, and fatal blockers.
7. Sensitivity analysis and main value drivers.
8. Evidence gaps and risks.
9. Next validation steps with measurable acceptance criteria.

For every important number, label its source or status as **verified**, **provided**, **estimated**, or **assumed**. If external research is available, prioritize primary sources, technical papers, lifecycle studies, regulatory documents, audited company disclosures, and observed project data.

## Decision language

End with a conditional, operational conclusion. Prefer: “The technology is attractive if X, Y, and Z are demonstrated” over an unconditional claim. Identify the smallest next experiment, pilot, procurement test, or financial validation that could change the decision.

Use the detailed indicator definitions and scoring rubric in [references/evaluation-rubric.md](references/evaluation-rubric.md) when a full assessment or reusable report is requested.
