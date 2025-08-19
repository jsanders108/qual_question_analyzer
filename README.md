# AG2: Dynamic Survey Question Analyzer

## Overview & Background

**The Challenge**:
In real-world market research and organizational settings, analysts often face **unstructured survey inputs**. The wording and structure of survey questions are not always known in advance, which makes it difficult to predefine analytical workflows. Traditional methods require manual parsing, theming, and report writing, which are time-intensive and inconsistent.

**The Solution**:
This project demonstrates how **AG2 multi-agent workflows** can dynamically analyze a survey question **on the fly**. Instead of relying on pre-scripted analysis logic, the system adapts by:

* **Planning** an analysis approach tailored to the question wording and dataset.
* **Executing** the analysis according to that plan.
* **Producing** a professional market-research-style report through iterative draft → review → revision → finalization.

The included demonstration uses a **synthetic dataset** (AI-generated survey responses) on beer brand preferences, showcasing how the workflow handles open-ended qualitative questions in practice【8†final\_question\_report.md】.

---

## Survey Question Example

The synthetic survey asked respondents:

**“Name the beer brand you buy most often in cans. Why do you usually choose this brand? Why sometimes another brand?”**

**Dataset**:

* 18 synthetic responses stored in `data/mock_beer_data.csv`【8†mock\_beer\_data.csv】
* Responses include both **main brand choices** and **reasons for switching**

**Special Note on Dataset Size**:
The dataset in this demo contains only **18 responses**, because the real-world case this project was modeled on was a **pre-focus group survey question**, given to participants before their group sessions began. In such contexts, **small-N analysis** is often the norm.

That said, the workflow is **adaptable to larger datasets** (e.g., hundreds of responses). For scalability, the structure may need modification — such as chunking responses or avoiding injection of all rows into a single system message.

**Sample Insights** (from the generated report【8†final\_question\_report.md】):

* Budweiser and Coors emerged as the leading brands (each with 33%).
* Drivers of choice: taste, tradition, and availability.
* Switching occurred mainly due to desire for variety (56%) or stock issues (39%).
* Implications for marketers: emphasize taste and tradition while planning for variety-driven trial.

---

## Who This Is For

* **Market Researchers** needing rapid, adaptive survey analysis
* **Consultants & Agencies** handling varied client questions
* **Data Scientists** interested in reproducible, AI-driven workflows
* **Product & Strategy Teams** requiring flexible, decision-ready insights

---

## Workflow Overview

The system is orchestrated by **`generate_question_report.py`**【9†generate\_question\_report.py】, which coordinates a multi-agent pipeline:

### 1. **Planning Stage**

* The **analysis planner agent** creates a tailored plan:

  * Parsing logic for responses
  * Theming & classification rules
  * Quantification methods (e.g., n/total counts)
  * Quote selection guidelines
  * Final deliverable structure

---

### 2. **Drafting Stage**

* The **report drafter agent** follows the plan exactly.
* Produces a structured **first draft report** in Markdown.

---

### 3. **Reviewing Stage**

* The **reviewer agent** checks:

  * Plan compliance
  * Thematic accuracy & evidence
  * Clarity and neutrality
* Provides structured feedback (with severity ratings & recommendations).

---

### 4. **Revising Stage**

* The **reviser agent** incorporates reviewer feedback.
* Documents changes made.
* Can loop back for multiple review cycles.

---

### 5. **Finalizing Stage**

* The **final report agent** delivers a **client-ready report**:

  * Executive Summary first
  * Tables & illustrative quotes
  * Strategic implications clearly surfaced
* Outputs `final_question_report.md`

---

## Iterative Feedback Loop (Quality First)

The project enforces quality through **staged iteration**:

**Stages**:

1. **Create Plan** – AI designs the analysis approach
2. **Draft** – AI produces a full first draft
3. **Review** – AI checks for completeness and rigor
4. **Revise** – AI applies targeted improvements
5. **Finalize** – AI polishes into a decision-ready report

**Quality gates**:

* Accurate reflection of data
* Thematic clustering validated
* Quotes correctly attributed
* Final report ends with `# End of Report`【8†final\_question\_report.md】

---

## System Architecture

### Entry Point (`generate_question_report.py`)

* Orchestrates entire pipeline across all agents
* Loads CSV input and survey question
* Handles stage transitions

### Agents

* **Analysis Planner** – defines methodology
* **Report Drafter** – applies methodology
* **Reviewer** – enforces rigor
* **Reviser** – improves based on feedback
* **Finalizer** – delivers polished report

### Data

* `mock_beer_data.csv` – synthetic survey data
* `final_question_report.md` – final polished output

---

## Running the Project

### 1. Install Dependencies

```bash
pip install autogen python-dotenv pydantic
```

### 2. Set Your API Key

Create a `.env` file:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. Ensure Required Inputs

* Survey CSV file (`data/mock_beer_data.csv`)
* A survey question text (hardcoded in script or replace with your own)

### 4. Run the Workflow

```bash
python generate_question_report.py
```

---

## Outputs

After running, you’ll have:

* **Draft Reports** (internal to workflow)
* **Final Report**:

  * `final_report/final_question_report.md`

---

## Conclusion

This project showcases how **AG2 multi-agent workflows** can transform survey analysis when question structures are **unknown upfront**:

* **Adaptive** – Agents dynamically create an analysis plan based on question/data
* **Efficient** – Produces rigorous reports in minutes, not days
* **Reliable** – Built-in review/revision cycle ensures quality
* **Professional** – Output is client-ready, with executive insights leading

By automating analysis planning, execution, and synthesis, AG2 enables analysts to handle **any survey question dynamically**, freeing them to focus on interpretation and strategy.
