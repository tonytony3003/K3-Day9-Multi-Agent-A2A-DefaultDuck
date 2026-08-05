# Multi-Agent Architecture for E-Commerce Dispute Resolution

## 1. Overview
The system processes 50 JSON customer requests in parallel, analyzes claims against data from the Olist datasets, and automatically outputs financial resolutions and actions in structured JSON format using multiple autonomous agents.

## 2. Agent Roles & Responsibilities

- **Coordinator / Data Fetcher Agent (Python Code)**:
  - Takes the incoming customer request (JSON).
  - Extracts the `claimed_order_id`.
  - Queries `orders`, `order_items`, `order_payments`, and `sellers` datasets using pandas.
  - Formats raw data into structured inputs for other downstream LLM agents.
  - Aggregates final data to pass to the Verifier.

- **Order & Seller Agent (LLM)**:
  - Takes order status and items context.
  - Determines if the order is canceled or unavailable.
  - Identifies if sellers shipped the order items after their specific `shipping_limit_date`.

- **Delivery Agent (LLM)**:
  - Takes the overall order timeline context.
  - Assesses whether the package was delivered to the customer late (after `order_estimated_delivery_date`).
  - Checks if the carrier received the package from sellers late.

- **Payment Agent (LLM)**:
  - Reconciles total payments against total items and freight values.
  - Determines if the user made valid split payments and whether the mathematical check balances out within the 0.10 BRL tolerance.

- **Policy Agent (LLM)**:
  - Absorbs the findings from the previous three agents.
  - Steps through the prioritized rules (EC_POLICY_V1) to figure out the `primary_issue`.
  - Determines if `action_required` is needed and calculates `recommended_refund_brl` alongside actionable tasks (`refund_freight`, `issue_full_refund`, etc).
  - Assesses `confidence` based on clarity of the extracted dataset.

- **Verifier Agent (Python Code)**:
  - Strictly enforces the limits set by the system (max 10 evidences, max 5 affected entities of any type, max 3 root causes/parties).
  - Writes standard output safely to JSON format in the `output/` directory.

## 3. Data Flow

1. **Input JSON** -> Coordinator Agent.
2. Coordinator extracts data from memory -> `Order & Seller`, `Delivery`, and `Payment` Agents.
3. Outputs of sub-agents -> `Policy Agent`.
4. Output of Policy Agent -> `Verifier Agent`.
5. Output of Verifier Agent -> `output/EC_xxx.json`.

## 4. Handoff Mechanisms
- The handoff is done using strongly typed `Pydantic` JSON schemas parsing directly into `OpenAI API (gpt-4o-mini)`. This minimizes prompt-injection or hallucination issues and ensures each Agent receives exact schemas needed for evaluation.