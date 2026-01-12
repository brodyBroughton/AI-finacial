"""Analyze 10-Q Item 2 data and return structured insights."""

from edgar import set_identity
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
import os
from toolsmod import cache_fetcher, edgar_fetcher


def model_init():
    """Initialize analysis and judge models using environment variables."""

    load_dotenv()
    missing = [key for key in ("OPENAI_API_KEY", "GOOGLE_API_KEY") if not os.environ.get(key)]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")

    class Judge(BaseModel):
        """Schema describing the Gemini judge response payload."""

        passorfail: str = Field(
            description=(
                " I want you to print a 'pass' or 'fail' in the 'passorfail' make"
                " sure to not write anything else exept 'pass' or 'fail'"
            )
        )
        anomalies: str = Field(
            description=(
                "and if the report fails write your concutions for the"
                " incorrectness of the report in the anomalies section. "
            )
        )

    model = ChatOpenAI(
        model="gpt-5-mini",
        max_tokens=None,
        timeout=None,
        max_retries=2,
        temperature=0.0,
    ).with_structured_output(method="json_mode")

    judge_model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
        max_tokens=None,
        timeout=None,
        max_retries=2,
    ).with_structured_output(Judge, method="json_mode")
    return model, judge_model


def fetch_item2(ticker: str, use_cache: bool = True):
    """Fetch Item 2 content either from cache or directly via EDGAR."""

    user_agent = os.environ.get("SEC_USER_AGENT", "jacob casey jacobrcasey135@gmail.com")
    set_identity(user_agent)

    if use_cache:
        cached = cache_fetcher(ticker)
        if cached:
            return cached

    return edgar_fetcher(ticker)


def revenue_llm(tenqitem2cont: str):
    """Generate the revenue analysis JSON report."""

    model, _ = model_init()

    msg = [
        HumanMessage(
            content= f"""
    INPUT: you will be given the entire item 2 of a 10-q form 
    
    
    here is the form: "{tenqitem2cont}"

            """ + """


    --ROLE: You are a expert finacial analyst that specilises in reading and understanding 10-q and specificly the revenues

    --JOB: review the content to determine why the company's revenues increase/decrease Did it increase its sales from increased sales and 
    services (organic) or was it from an aquisition, gants or settlements (inorganic)? 


    --OUTPUT INSTRUCTIONS: 
    -I want you to do a revenue analisys of the text provided what did the company do to lose or gain revenue 
    -quote numbers from the provided texts to back up your claims of revenue gain or loss inside the respective json sections. 
    -make sure when you are doing the revenue streams and growth type to list the streams from highest gain to lowest so majority revenue to least majority.
    -quote the quarter time frame for each change in revenue in the drive section after the amount or percentage is stated.
    -if a number is in thousands make sure to state that the number is in thousands
    -the instructions for each section will be listed below. 
    -YOU MUST FOLLOW THE JSON FORMATTING BELOW EXACTLY THE ONLY CHAGES YOU CAN MAKE IS REPEAT THE SECTIONS THAT SAY IN THE DESCRIPTIONS THAT THEY CAN BE REPEATED
    
    --OUTPUT SCHEMA AND OUTPUT INSTRUCTIONS (JSON) = { 
    "company name": "name of the company",
    "headline result": "what is the general report of the revenue losses or gains this is a summary section", 
    "what drove the revenue change": "what are the main drivers of the revenue changes loss or gain",
    "revenue streams and growth type": { 
        "revenue stream": "this is detailed what is the specific revenue stream you are analising you should repeat this for every stream of revenue. MAKE SURE TO INCLUDE EVERY STATED REVENUE STREAM FROM THE 10-Q EXACTLY",
        "driver": "what is the gain or loss of revenue and why did this specific revenue stream gain or lose money you should repeat this for every driver for every stream",
        "organic or inorganic": "was the gain or loss in revenue organic or inorganic (orgainic is repetable growth or loss. and inorganic is one time events that are not likely repetable gain or loss) you should repeat this for every previous driver and stream.",
        },
    }

    """,
        )
    ]

    return model.invoke(msg)


def gemini_judge_revenue(tenqitem2cont: str, revenue_report):
    """Validate the revenue report and return the judge response."""

    _, judge_model = model_init()

    msg = [
        HumanMessage(
            content= f"""
    INPUT: you will be given the entire item 2 of a 10-q form 
    
    
    here is the form: "{tenqitem2cont}"

    here is the first llm's revenue response to this document: "{revenue_report}"

            """ + """


    --ROLE: You are a expert finacial analyst that specilises in judging a llm's output 

    --JOB: review the content to determine if the revenue report is correct for the given section of the 10-q form


    --OUTPUT INSTRUCTIONS: I want you to print a "pass" or "fail" in the "passorfail" make sure to not write anything else exept "pass" or "fail" and if the report fails 
    write your concutions for the incorrectness of the report in the anomalies section. 

    --OUTPUT FORMAT = { 
    "passorfail": "your response here", 
    "anomalies": "your response here",
    }
    """,
        )
    ]

    revenue_judge_report = judge_model.invoke(msg)
    if revenue_judge_report.passorfail == 'fail':
        print("this report has failed")
        print("anomalies:", revenue_judge_report.anomalies)
    return {
        "passorfail": revenue_judge_report.passorfail,
        "anomalies": revenue_judge_report.anomalies,
    }


def cashflow_llm(tenqitem2cont: str):
    """Generate the cashflow analysis JSON report."""

    model, _ = model_init()

    msg = [
        HumanMessage(
            content= f"""
    INPUT: you will be given the entire item 2 of a 10-q form 
    
    
    here is the form: "{tenqitem2cont}"

            """ + """


    --ROLE: You are a expert finacial analyst that specilises in reading and understanding 10-q and specificly the cashflows

    --JOB: review the content to determine why the company's cashflow increase/decrease Did cashflow increased from sales and 
    services (organic) or was it from an aquisition, gants or settlements (inorganic)? 


    --OUTPUT INSTRUCTIONS: 
    -I want you to do a cashflow analisys of the text provided what did the company do to lose or gain operating chashflow.
    -quote numbers from the provided texts to back up your claims of cashflow gain or loss inside the respective json sections.
    -quote the quarter time frame for each change in cashflow in the drive section after the amount or percentage is stated.
    -if a number is in thousands make sure to state that the number is in thousands
    -the instructions for each section will be listed below.
    -DO NOT ADD ANY EXTRA SECTIONS TO THE JSON FORMATTING
    
    --OUTPUT SCHEMA AND OUTPUT INSTRUCTIONS (JSON) = {
    "company name": "name of the company",
    "headline result": "what is the general report of the cashflow losses or gains this is a summary section", 
    "cashflow and growth type": { 
        "operating cashflow": "this is a summary of operating cashflow. is it negitive or positive.",
        "driver": "what is the gain or loss of operating cashflow and why did this metric gain or lose money",
        },
    }

    """,
        )
    ]

    return model.invoke(msg)


def gemini_judge_cashflow(tenqitem2cont: str, cashflow_report):
    """Validate the cashflow report and return the judge response."""

    _, judge_model = model_init()

    msg = [
        HumanMessage(
            content= f"""
    INPUT: you will be given the entire item 2 of a 10-q form 
    
    
    here is the form: "{tenqitem2cont}"

    here is the first llm's cashflow response to this document: "{cashflow_report}"

            """ + """


    --ROLE: You are a expert finacial analyst that specilises in judging a llm's output 

    --JOB: review the content to determine if the cashflow report is correct for the given section of the 10-q form


    --OUTPUT INSTRUCTIONS: I want you to print a "pass" or "fail" in the "passorfail" make sure to not write anything else exept "pass" or "fail" and if the report fails 
    write your concutions for the incorrectness of the report in the anomalies section. 

    --OUTPUT FORMAT = { 
    "passorfail": "your response here", 
    "anomalies": "your response here",
    }
    """,
        )
    ]

    cashflow_judge_report = judge_model.invoke(msg)
    if cashflow_judge_report.passorfail == 'fail':
        print("this report has failed")
        print("anomalies:", cashflow_judge_report.anomalies)
    return {
        "passorfail": cashflow_judge_report.passorfail,
        "anomalies": cashflow_judge_report.anomalies,
    }


def debt_llm(tenqitem2cont: str):
    """Generate the debt analysis JSON report."""

    model, _ = model_init()

    msg = [
        HumanMessage(
            content= f"""
    INPUT: you will be given the entire item 2 of a 10-q form 
    
    
    here is the form: "{tenqitem2cont}"

            """ + """


    --ROLE: You are a expert finacial analyst that specilises in reading and understanding 10-q and specificly the debt

    --JOB: review the content to determine why the company's debt increase/decrease Did it increase its debt, was the debt good or bad debt


    --OUTPUT INSTRUCTIONS: 
    -I want you to do a debt analisys of the text provided what did the company do to lose or gain debt 
    -quote numbers from the provided texts to back up your claims of debt gain or loss inside the respective json sections. 
    -make sure when you are doing the debt sections list highest source of debt to lowest source of debt
    -quote the quarter time frame for each change in debt in the drive section after the amount or percentage is stated.
    -if a number is in thousands make sure to state that the number is in thousands
    -the instructions for each section will be listed below. 
    -DO NOT ADD ANY EXTRA SECTIONS TO THE JSON FORMATTING.
    
    --OUTPUT SCHEMA AND OUTPUT INSTRUCTIONS (JSON) = { 
    "company name": "name of the company",
    "what_changed_with_debt": "<e.g., 'Debt fell by ~$200M due to repayment' or 'Debt rose ~$500M from new notes'>",
    "why_it_changed": "<brief reason — refinancing, working capital, acquisition, etc.>",
    "can_they_pay_bills": "<near-term cash sources/uses; include revolver availability>",
    "management_plan": "<how they plan to fund needs — operations, revolver, refinance, asset sales, equity>",
    }

    """,
        )
    ]

    return model.invoke(msg)


def gemini_judge_debt(tenqitem2cont: str, debt_report):
    """Validate the debt report and return the judge response."""

    _, judge_model = model_init()

    msg = [
        HumanMessage(
            content= f"""
    INPUT: you will be given the entire item 2 of a 10-q form 
    
    
    here is the form: "{tenqitem2cont}"

    here is the first llm's debt report to this document: "{debt_report}"

            """ + """


    --ROLE: You are a expert finacial analyst that specilises in judging a llm's output 

    --JOB: review the content to determine if the debt report is correct for the given section of the 10-q form


    --OUTPUT INSTRUCTIONS: I want you to print a "pass" or "fail" in the "passorfail" make sure to not write anything else exept "pass" or "fail" and if the report fails 
    write your concutions for the incorrectness of the report in the anomalies section. 

    --OUTPUT FORMAT = { 
    "passorfail": "your response here", 
    "anomalies": "your response here",
    }
    """,
        )
    ]

    debt_judge_report = judge_model.invoke(msg)
    if debt_judge_report.passorfail == 'fail':
        print("this report has failed")
        print("anomalies:", debt_judge_report.anomalies)
    return {
        "passorfail": debt_judge_report.passorfail,
        "anomalies": debt_judge_report.anomalies,
    }


def run_orgvsinorg(ticker: str, use_cache: bool = True) -> dict:
    """Run the full analysis pipeline for ``ticker``."""

    fetched = fetch_item2(ticker, use_cache=use_cache)
    if not fetched:
        return {}

    tenqitem2cont, stockinfo = fetched

    revenue_report = revenue_llm(tenqitem2cont)
    gemini_judge_revenue(tenqitem2cont, revenue_report)

    cashflow_report = cashflow_llm(tenqitem2cont)
    gemini_judge_cashflow(tenqitem2cont, cashflow_report)

    debt_report = debt_llm(tenqitem2cont)
    gemini_judge_debt(tenqitem2cont, debt_report)

    return {
        "revenue": revenue_report,
        "cashflow": cashflow_report,
        "debt": debt_report,
        "stockinfo": stockinfo,
    }


if __name__ == "__main__":
    print(run_orgvsinorg("rddt", use_cache=True))
