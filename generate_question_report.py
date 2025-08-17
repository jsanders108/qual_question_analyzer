
from dotenv import load_dotenv
import os
from pathlib import Path
import csv


from autogen.agentchat.group import AgentTarget, ContextVariables, ReplyResult, TerminateTarget, OnContextCondition, ExpressionContextCondition 
from autogen import UserProxyAgent, ConversableAgent, LLMConfig, UpdateSystemMessage, ContextExpression
from autogen.agentchat.group.patterns import DefaultPattern
from autogen.agentchat import initiate_group_chat
from pydantic import BaseModel
from typing import Annotated, Optional
from enum import Enum


# Load environment variables from .env file (expects OPENAI_API_KEY)
load_dotenv()


def generate_question_report(): 
    
    model="gpt-4.1"


    # ---------------------------
    # Create output directory
    # ---------------------------
    #out_dir = Path("final_report")
    #out_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------
    # Configure LLM parameters
    # ---------------------------
    llm_config = LLMConfig(
        api_type="openai",
        model=model,
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0, # deterministic output
        cache_seed=None,
        tool_choice="required" 
    )

        # ---------------------------
    # Enum for workflow stage tracking
    # ---------------------------
    class ReportStage(str, Enum):
        PLANNING = "planning"
        DRAFTING = "drafting"
        REVIEWING = "reviewing"
        REVISING = "revising"
        FINALIZING = "finalizing"

    # ---------------------------
    # Shared context variables
    # ---------------------------
    shared_context = ContextVariables(data={
        # Feedback loop state
        "loop_started": False,
        "current_iteration": 0,
        "max_iterations": 1,
        "iteration_needed": True,
        "current_stage": ReportStage.PLANNING.value,

        # Report data at various stages
        "question_text": "",
        "csv_headers": [],
        "csv_rows": [],
        "csv_rows_total": 0,
        "csv_text": "",
        "analysis_plan": "",
        "report_draft": "",
        "feedback_collection": {},
        "revised_report": {},
        "final_report": "",

    })

   

    csv_path = "data/mock_beer_data.csv"

    # Raw text (optional)
    csv_text = Path(csv_path).read_text(encoding="utf-8")

    # Structured rows + headers
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)

    # Store in context (must be JSON-serializable)
    shared_context["csv_headers"] = headers
    shared_context["csv_rows"] = rows              # full dataset is tiny, safe to include
    shared_context["csv_rows_total"] = len(rows)
    shared_context["csv_text"] = csv_text          # optional, avoid injecting unless you need it



    # Stage 1: Start the report process
    def kickoff_question_report_process(question_text: str, context_variables: ContextVariables) -> ReplyResult:
        """
        Start the question report process and advance to PLANNING stage.
        """
        context_variables["question_text"] = question_text
        context_variables["current_stage"] = ReportStage.PLANNING.value
        context_variables["current_iteration"] = 1
        context_variables["loop_started"] = True
        return ReplyResult(
            message="Question report process started. Moving to planning stage.",
            target=AgentTarget(analysis_planner_agent),
            context_variables=context_variables,
        ) 


    # Stage 2: Planning
    def submit_analysis_plan(analysis_plan: Annotated[str, "Full text content of the analysis plan"], 
                            context_variables: ContextVariables) -> ReplyResult:
        """
        Submit the analysis plan and advance to DRAFTING stage.
        """
        context_variables["analysis_plan"] = analysis_plan
        context_variables["current_stage"] = ReportStage.DRAFTING.value
        return ReplyResult(
            message="Analysis plan submitted. Moving to drafting stage.",
            target=AgentTarget(report_drafter_agent),
            context_variables=context_variables,
        )


    # Stage 3: Drafting
    def submit_report_draft(content: Annotated[str, "Full text content of the report draft"],
                            context_variables: ContextVariables) -> ReplyResult:
        """Submit the initial report draft and advance to REVIEWING stage."""
        context_variables["report_draft"] = content
        context_variables["current_stage"] = ReportStage.REVIEWING.value
        return ReplyResult(
            message="Report draft submitted. Moving to reviewing stage.",
            target=AgentTarget(report_reviewer_agent),
            context_variables=context_variables,
        )


    # Stage 4: Reviewing
    class FeedbackItem(BaseModel):
        section: str
        feedback: str
        severity: str
        recommendation: Optional[str]

    class FeedbackCollection(BaseModel):
        items: list[FeedbackItem]
        overall_assessment: str
        priority_issues: list[str]
        iteration_needed: bool

    def submit_feedback(items: Annotated[list[FeedbackItem], "Collection of feedback items"],
                        overall_assessment: Annotated[str, "Overall assessment of the report"],
                        priority_issues: Annotated[list[str], "List of priority issues to address"],
                        iteration_needed: Annotated[bool, "Whether another iteration is needed"],
                        context_variables: ContextVariables) -> ReplyResult:
        """Submit reviewer feedback and advance to revising stage."""
        feedback = FeedbackCollection(
            items=items,
            overall_assessment=overall_assessment,
            priority_issues=priority_issues,
            iteration_needed=iteration_needed
        )
        context_variables["feedback_collection"] = feedback.model_dump()
        context_variables["iteration_needed"] = feedback.iteration_needed
        context_variables["current_stage"] = ReportStage.REVISING.value
        return ReplyResult(
            message="Feedback submitted. Moving to revising stage.",
            context_variables=context_variables,
        )


    # Stage 5: Revising
    class RevisedReport(BaseModel):
        content: str
        changes_made: Optional[list[str]]

    def submit_revised_report(content: Annotated[str, "Full text content after revision"],
                              changes_made: Annotated[Optional[list[str]], "List of changes made based on feedback"],
                              context_variables: ContextVariables) -> ReplyResult:
        """Submit revised report and either loop back to REVIEWING or advance to FINALIZING stage."""
        revised = RevisedReport(content=content, changes_made=changes_made)
        context_variables["revised_report"] = revised.model_dump()
        context_variables["report_draft"] = revised.content

        if context_variables["iteration_needed"] and context_variables["current_iteration"] < context_variables["max_iterations"]:
            context_variables["current_iteration"] += 1
            context_variables["current_stage"] = ReportStage.REVIEWING.value
            return ReplyResult(
                message=f"Report revised. Starting iteration {context_variables['current_iteration']} with another review.",
                context_variables=context_variables,
            )
        else:
            context_variables["current_stage"] = ReportStage.FINALIZING.value
            return ReplyResult(
                message="Revisions complete. Moving to finalizing stage.",
                target=AgentTarget(final_report_agent),  
            context_variables=context_variables,
        )



    # Stage 6: Finalizing
    def submit_final_report(content: Annotated[str, "Full text content of the final report"],
                        context_variables: ContextVariables) -> ReplyResult:
        """Submit the final report and terminate workflow."""
        context_variables["final_report"] = content
        context_variables["iteration_needed"] = False
        context_variables["current_stage"] = "done" 
        return ReplyResult(
            message="Report finalized ✅ - terminating workflow.",
            target=TerminateTarget(),
            context_variables=context_variables,
        )



    # ---------------------------
    # Agent definitions
    # ---------------------------
    with llm_config:
        # Kickoff → Planning → Draft → Review → Revision → Finalization
        kickoff_agent = ConversableAgent(
            name="kickoff_agent",
            system_message="""
            ROLE: You are the kickoff agent. You only initialize the workflow.

            TASK: Call kickoff_question_report_process(question_text, context_variables).

            DO NOT: analyze data, draft plans, or produce narrative.
            """,
            functions=[kickoff_question_report_process]
        )

        analysis_planner_agent = ConversableAgent(
            name="analysis_planner_agent",
            system_message="""You are the analysis planner agent.""",
            functions=[submit_analysis_plan],
            update_agent_state_before_reply=[UpdateSystemMessage("""
            ROLE:
            You are the analysis planner agent. Your sole job is to design a comprehensive, step-by-step plan 
            for analyzing the data for a single survey question. You DO NOT analyze the data yourself.

            TOOLS:
            • submit_analysis_plan(analysis_plan: str, context_variables: ContextVariables) — Submit your completed analysis plan.

            CONTEXT:
            Recently a survey question was fielded to consumers.
            Here is the text of the question:
            {question_text}

            PRIMARY TASK:
            Create a detailed plan for a comprehensive analysis of the data based on the question and data provided. 
            Do not analyze the data; just create the plan.
            

            WORKFLOW & REQUIREMENTS:
            1) Read the data. The data is provided in csv format below (headers and rows):
            {csv_headers}
            {csv_rows}

            The total number of rows is:
            {csv_rows_total}
            

            2) Design the analysis plan tailored to the question and data provided:
            - Define parsing instructions (e.g.,how to segment responses, what units of meaning to extract).
            - Define classification rules, labels, and decision criteria (e.g., directional buckets, mutually exclusive vs. multi-label coding).
            - Specify clustering/theming steps and consolidation logic (e.g., when to merge/split themes; max theme count if applicable).
            - Describe light quantification expectations (**counts with total sample size**, e.g., 4/15, where 4 = number of respondents mentioning a theme and 15 = total who answered).
            - Set guidance for selecting illustrative quotes (e.g., how many, attribution format).
            - Include narrative synthesis expectations (how to integrate drivers/deterrents, segments/contexts, contradictions).
            - Define the final deliverable structure (tables/sections/labels) that the drafting agent should produce.

            3) Keep the plan specific to the question and data provided.
            - Mirror the structure and rigor of the example below, but adapt the details to this question.
            - Do not invent findings or themes; the plan should only prescribe how to derive them.

            EXAMPLE OF AN APPROPRIATE PLAN:
            --------------------------
            A group of respondents were asked the following survey question (Q1):

            "Generally speaking, name 2-3 reasons why you (occasionally) choose beer in a can instead of a bottle.  
            Also, name 2-3 reasons why you choose not to go for a can (and instead choose a bottle)?"
            
            **Your Task -- Summarize and Analyze Qualitative Feedback:**
            1. **Collect the data using the read_question_data function.**

            2. **Parse responses into two directional buckets (per question wording):**
            - **Reasons FOR choosing a can (vs. bottle)** — what makes respondents *occasionally* opt for canned beer.
            - **Reasons AGAINST a can / FOR choosing a bottle** — what deters them from cans and pushes them toward bottles.  
            Capture nuance: some respondents may list multiple reasons on both sides; parse all distinct points.

            3. **Cluster into themes.** Review all parsed reasons and group similar ideas. Identify **up to five total key themes** spanning both sides of the choice (e.g., *Portability & Packability*, *No-Glass / Safety & Venue Rules*, *Temperature & Chill Speed*, *Taste / Perceived Quality*, *Environmental or Recycling Views*, *Social Image / Occasion Fit*, *Metallic Flavor Concerns*, etc.). Combine closely related micro-reasons so themes are meaningful but not redundant. If fewer than five emerge clearly, report only the themes that are well supported.

            4. **Quantify light touch.** For each theme, note prevalence using counts with total sample size — formatted as n/total (e.g., 4/15, where 4 = number of respondents mentioning the theme and 15 = total respondents who answered the question). Counts should include mentions on either side; specify whether the theme is a *pro-can driver*, *anti-can (pro-bottle) deterrent*, or *mixed* (both).

            5. **Select illustrative quotes.** For every theme, include **one or two short, high-impact verbatim quotes** that best convey respondents’ reasoning. Each quote must include the respondent’s name/ID and be labeled as *pro-can* or *anti-can* (when clear). Lightly clean typos only if needed for readability; mark edits with square brackets if you change wording.

            6. **Respect the tone requested by Q1 summary style:**
            - Because Q1 explicitly asks for *both* “why choose a can” **and** “why not (choose bottle instead),” your write-up **must clearly present both positive (pro-can) and negative (anti-can / pro-bottle) insights.**
            - If the raw data skews heavily one way, state that, but still surface minority views from the other side if present.

            7. **Synthesize narrative.** After the theme table/sections, provide a concise narrative that:
            - Summarizes the major drivers of *occasional* can choice.  
            - Summarizes the major deterrents pushing respondents toward bottles.  
            - Highlights context modifiers (occasion, location rules, portability needs, taste expectations, sustainability perceptions, etc.) when they influence directionality.  
            - Notes any interesting respondent segments or contradictions (e.g., people praising portability but complaining about taste).

            expected_output: >
            Provide a structured qualitative analysis including:

            - **Theme Summary Table (recommended):** Theme name; Direction (Pro-Can / Anti-Can / Mixed); n respondents / total respondents (e.g., 4/15); short insight sentence.
            - **Theme Detail Sections:** Brief analytic paragraph + 1-2 attributed quotes each.
            - **Overall Narrative:** Integrates both sides, reflects tone and frequency patterns, and references that Q1 asked explicitly for both pro-can and anti-can reasons.
            ---------------

            OUTPUT:
            A complete, tailored analysis plan in clear, scannable markdown that specifies:
            - Parsing logic and directional buckets (if relevant)
            - Theming/cluster methodology and any limits
            - Light quantification approach (**counts with total respondents**, formatted n/total)
            - Quote selection rules and attribution format
            - Narrative synthesis expectations
            - Any quality checks and edge-case handling
            - Final deliverable structure the drafting agent should follow

            SUBMISSION:
            After you have created the plan, you MUST submit the plan by using the *submit_analysis_plan* function.

            """)
                
            ]
        )

        report_drafter_agent = ConversableAgent(
            name="report_drafter_agent",
            system_message="""You are the report drafter agent.""",
            functions=[submit_report_draft],
            update_agent_state_before_reply=[UpdateSystemMessage("""
            
            ROLE:  
            You are the report drafter agent. Your job is to transform raw survey responses 
            into a clear, structured first draft report by strictly following the provided analysis plan.  

            TOOLS:   
            • submit_report_draft(content: str, context_variables: ContextVariables) — Submit your completed draft report.  

            INPUTS:  
            • {question_text} — The survey question being analyzed.   

            TASK:  
            1. Read the data. The data is provided in csv format below (headers and rows):
            {csv_headers}
            {csv_rows}

            The total number of rows is:
            {csv_rows_total}

            2. **Follow the analysis plan exactly**  
            Here is the analysis plan:
            ---
            {analysis_plan}
            ---

            - Parse responses as instructed.  
            - Categorize, cluster, and theme according to the plan.  
            - Apply any specific definitions, labels, or classification rules given.  
            - Quantify, summarize, and select illustrative quotes exactly as the plan directs.  

            3. **Craft the full draft report**  
            - Include all required sections in the exact structure specified in the plan.  
            - Maintain the tone, perspective, and focus requested in the plan.  
            - If the plan specifies a table, ensure the table is complete and correctly formatted. Avoid using percentages in tables. 
            Instead, use counts and total sample sizes (e.g., 4/15, where 4=number of respondents mentioning a theme and 15=total number of respondents who
            answered the question)
            - Clearly differentiate between directional categories (e.g., pro, anti, mixed) if required.  

            4. **No omissions or inventions**  
            - Do **not** add themes, insights, or quotes not supported by the data.  
            - If something in the plan is not applicable to the data, note that explicitly in the report rather than skipping it without explanation.  

            OUTPUT:  
            A complete, polished draft report in *markdown* format that fully meets the expectations of the analysis plan and is ready for review.

            SUBMISSION:
            After you have created the draft report, you MUST submit the draft report by using the *submit_report_draft* function.

            """)],
        )



        report_reviewer_agent = ConversableAgent(
            name="report_reviewer_agent",
            system_message="You are the report reviewer agent.",
            functions=[submit_feedback],
            update_agent_state_before_reply=[UpdateSystemMessage("""
            ROLE:  
            You are the report reviewer agent responsible for critical evaluation.

            YOUR TASK:  
            Perform a rigorous, constructive evaluation of the report draft to ensure 
            it fully satisfies the original plan and accurately reflects the data.

            TOOLS:  
            • submit_feedback(items: list[FeedbackItem], overall_assessment: str, priority_issues: list[str], iteration_needed: bool, context_variables: ContextVariables) - Submit structured feedback.

            WORKFLOW-(complete in order):  
            1. **Gather Context**  
               a. Read the data. The data is provided in csv format below (headers and rows):
               {csv_headers}
               {csv_rows}

               The total number of rows is:
               {csv_rows_total}
               b. Review the report draft : {report_draft}  
               c. Review the analysis plan : {analysis_plan}

            2. **Evaluate the report draft** against:  
               • Analysis plan compliance & completeness  
               • Thematic accuracy and evidence support 
               • Clarity, logic, and flow of writing  
               • Neutrality and stakeholder-friendliness  

            3. **Provide Feedback**
                For the feedback you MUST provide the following:
                    1. items: list of feedback items (see next section for the collection of feedback items)
                    2. overall_assessment: Overall assessment of the draft report
                    3. priority_issues: List of priority issues to address
                    4. iteration_needed: Whether another iteration is needed (True or False)

                    For each item within feedback, you MUST provide the following:
                        1. section: The specific section the feedback applies to
                        2. feedback: Detailed feedback explaining the issue
                        3. severity: Rate as 'minor', 'moderate', 'major', or 'critical'
                        4. recommendation: A clear, specific action to address the feedback

                    Provide specific feedback with examples and clear recommendations for improvement.
                    For each feedback item, specify which section it applies to and rate its severity.

                    If this is a subsequent review iteration, also evaluate how well previous feedback was addressed.

            SUBMISSION:  
            After you have created your feedback, you MUST use the submit_feedback function to submit the feedback.
            """)]
        )



        report_reviser_agent = ConversableAgent(
            name="report_reviser_agent",
            system_message="""
            You are the report reviser agent.
            """,
            functions=[submit_revised_report],
            update_agent_state_before_reply=[UpdateSystemMessage("""
            ROLE: 
            You are the report reviser agent responsible for implementing feedback.

            OBJECTIVE:  
            Incorporate reviewer feedback to produce an improved Markdown report that still satisfies the original analysis plan.

            INPUTS:  
            • Current report draft: {report_draft} 
            • Feedback from report_reviewer_agent: {feedback_collection} 
            • Original analysis plan: {analysis_plan}
        
            TOOLS: 
            • submit_revised_report(content: str, changes_made: Optional[list[str]], context_variables: ContextVariables) - Submit the revised report.

            WORKFLOW (complete in order): 
            1. **Analyze Feedback**  
            • Sort feedback items by the reviewer's stated priority (or severity if no explicit order).  
            • Verify whether any item conflicts with the original analysis plan; if so, favor the original analysis plan 
            and note the conflict in the change log.

            2. **Revise the Report**  
            • Make targeted edits that directly address each feedback item.  
            • Preserve existing strengths and accurate content.  
            • Maintain all formatting constraints (e.g., no triple back-ticks; end with “# End of Report”).

            3. **Document Changes**  
            • Track and document the changes you make in a change log.

            SUBMISSION:  
            After you have created your revised report, you MUST use the submit_revised_report function to submit the revised report,
            as well as the change log.
            The revised report may go through multiple revision cycles depending on the feedback.
            """)]
        )



        final_report_agent = ConversableAgent(
            name="final_report_agent",
            system_message="""You are the final report agent.""",
            functions=[submit_final_report],
            update_agent_state_before_reply=[UpdateSystemMessage(
            """
            ROLE:
            You are the final report agent.  
            Your purpose is to transform a draft analysis into a polished, professional, client-ready Markdown report that 
            adheres to market research best practices — with strategic insights presented up front.

            PRIMARY OBJECTIVE:
            Deliver a final report that reads like a professional market research deliverable:
            - Clear executive-level takeaways at the start
            - Logical, reader-friendly flow
            - Professional language and formatting
            - Smooth transitions between sections
            - Ready for external delivery

            INPUTS:
            • {report_draft} — the latest report version, which may be complete but still reads like a working draft.

            OUTPUTS:
            • A fully restructured and polished Markdown report.
            • No triple backticks in the output.
            • End the report with exactly: "# End of Report"

            WORKFLOW
            1. **Assess and Plan Improvements**
            - Read through the draft and identify areas where flow, presentation, or tone is still “draft-like.”
            - Determine the logical section order, prioritizing decision-makers' needs.

            2. **Restructure to Lead with Insights**
            - Ensure the *Synthesis / Implications / Conclusion* section is placed at the **very beginning** of the report, immediately after the title and introduction.
            - Present this as an **Executive Summary** containing:
            - Key findings
            - Strategic implications
            - High-level recommendations or considerations
            - Follow with the supporting evidence sections.
            - Ensure that later detailed sections clearly connect back to the points raised in the Executive Summary.

            3. **Polish the Structure**
            - Ensure the report follows this logical order:
            1. Title
            2. Introduction (optional, short)
            3. Executive Summary (Synthesis, Implications, Conclusion)
            4. Detailed Findings
            5. Closing remarks or appendix (if applicable)
            - Add short introductory and wrap-up statements to each major section.

            4. **Refine the Language**
            - Rewrite for clarity, concision, and professional tone without altering facts or quotes.
            - Eliminate repetitive phrasing; vary sentence structure.
            - Ensure transitions between sections are smooth and guide the reader.

            5. **Enhance Professional Presentation**
            - Give each table a clear title and concise interpretive note.
            - Format quotes consistently, attributing them naturally in context.
            - Ensure all headings follow a consistent hierarchy.
            - Make percentages, counts, and formatting consistent across the report.
            - Avoid markdown artifacts that could break client formatting.

            6. **Final Review for Delivery**
            - Read as if you were the client: is it engaging, scannable, and decision-oriented?
            - Confirm the Executive Summary captures all critical insights so that a reader could stop there and still understand the findings.
            - Ensure there are no triple backticks, and the last line is exactly "# End of Report".


            REMEMBER:
            Your role is not just to “tidy” the draft — you are producing a **boardroom-ready market research report** where 
            the insights lead, and the supporting data follows.

            SUBMISSION:  
            After you have created your final report, you MUST use the submit_final_report function to submit the final report.

            """
            )]
        )




    # ---------------------------
    # Handoff logic between agents
    # ---------------------------
    kickoff_agent.handoffs.add_context_condition(
        OnContextCondition(
            target=AgentTarget(analysis_planner_agent),
            condition=ExpressionContextCondition(ContextExpression("${loop_started} == True and ${current_stage} == 'planning'"))
        )
    )
    
    analysis_planner_agent.handoffs.add_context_condition(
        OnContextCondition(
            target=AgentTarget(report_drafter_agent),
            condition=ExpressionContextCondition(ContextExpression("${current_stage} == 'drafting'"))
        )
    )

    report_drafter_agent.handoffs.add_context_condition(
        OnContextCondition(
            target=AgentTarget(report_reviewer_agent),
            condition=ExpressionContextCondition(ContextExpression("${current_stage} == 'reviewing'"))
        )
    )

    report_reviewer_agent.handoffs.add_context_condition(
        OnContextCondition(
            target=AgentTarget(report_reviser_agent),
            condition=ExpressionContextCondition(ContextExpression("${current_stage} == 'revising'"))
        )
    )

    report_reviser_agent.handoffs.add_context_conditions([
        OnContextCondition(
            target=AgentTarget(final_report_agent),
            condition=ExpressionContextCondition(ContextExpression("${current_stage} == 'finalizing'"))
        ),
        OnContextCondition(
            target=AgentTarget(report_reviewer_agent),
            condition=ExpressionContextCondition(ContextExpression("${current_stage} == 'reviewing'"))
        )
    ])

    final_report_agent.handoffs.set_after_work(TerminateTarget())

   
    # ---------------------------
    # Pattern orchestration
    # ---------------------------
    user = UserProxyAgent(name="user", code_execution_config=False)
    agent_pattern = DefaultPattern(
        initial_agent=kickoff_agent,
        agents=[kickoff_agent, analysis_planner_agent, report_drafter_agent, report_reviewer_agent, report_reviser_agent, final_report_agent],
        context_variables=shared_context,
        user_agent=user,
    ) 

    # ---------------------------
    # Run the multi-agent loop
    # ---------------------------
    chat_result, final_context, last_agent = initiate_group_chat(
        pattern=agent_pattern,
        messages="""
        A survey was fielded and the following question was asked:

        "Name the beer brand you buy most often in cans.
        Why do you usually choose this brand? Why sometimes another brand?"


        Please analyze the data based on the question.
        """,
        max_rounds=30 * shared_context["max_iterations"],
        
        ) 

    # ---------------------------
    # Save final output
    # ---------------------------
    if final_context.get("final_report"):
        print("Report creation completed successfully!")
        final_report_content = final_context['final_report']
        os.makedirs("final_report", exist_ok=True)
        with open("final_report/final_question_report.md", "w", encoding="utf-8") as f:
            f.write(final_report_content)
    else:
        print("Report creation did not complete successfully.")
       

if __name__ == "__main__":
    generate_question_report()