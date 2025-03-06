import os
import random
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from urllib.parse import quote

import requests
from jinja2 import Environment, FileSystemLoader

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Constants
GITLAB_API_URL = "https://git.esss.dk/api/v4"
DMSC_NIGHTLY_PROJECT_ID = 301
TOKEN = os.getenv("GITLAB_PRIVATE_TOKEN")
TEAMS = ["ECDC", "SCIPP", "SWAT", "DST", "DONKI", "IDS"]
INSTRUMENTS = ["bifrost", "dream", "estia", "loki", "nmx", "odin", "tbl", "none"]
GROUPS = [
    "chexus",
    "nexusfiles-scipp",
    "ingestor",
    "mcstas-scipp",
    "nexusjsontemplate-beamlime",
    "scipp-analysis",
    "scitacean",
]


# Data class for Job
@dataclass
class Job:
    job_run_url: str
    job_run_status: str
    job_name: str
    job_stage: str
    teams: str


# API Functions
def get_pipelines(project_id):
    # TODO: Add pagination or control number of pipelines to fetch
    url = f"{GITLAB_API_URL}/projects/{project_id}/pipelines?ref=main&source=schedule&per_page=5"
    logging.info(f"Fetching pipelines from URL: {url}")
    headers = {"Authorization": f"PRIVATE-TOKEN {TOKEN}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    pipelines = response.json()
    latest_pipeline = pipelines[0]
    # Get the last 50 pipeline ids
    last_50_pipelines = [
        (
            pipeline["id"],
            str(
                datetime.fromisoformat(pipeline["updated_at"].replace("Z", ""))
                + timedelta(hours=1)
            ),
        )
        for pipeline in pipelines[:50]
    ]
    return latest_pipeline, last_50_pipelines


def get_jobs(project_id, pipeline_id):
    url = f"{GITLAB_API_URL}/projects/{project_id}/pipelines/{pipeline_id}/jobs?per_page=100"
    headers = {"Authorization": f"PRIVATE-TOKEN {TOKEN}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def get_test_report(project_id, pipeline_id):
    url = f"{GITLAB_API_URL}/projects/{project_id}/pipelines/{pipeline_id}/test_report"
    headers = {"Authorization": f"PRIVATE-TOKEN {TOKEN}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    # logging.info(f"Fetching test report from URL: {url}")
    return response.json()


# char_map = {"success": "✅", "failed": "❌", "skipped": "⚠️", "error": "🚧"}
char_map = {"success": "✅", "failed": "❌", "skipped": "⚠️", "error": "-"}


def to_html(
    test_map, pipeline_run_ids, failing_test, skipped_tests, passing_tests, dates
):
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="3600">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DMSC Integration Testing</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head>
<body style="font-family: Tahoma, sans-serif;">
<div style="width: 100%; display: flex; background-color: #0094ca;">
<div style="flex:1;">
    <img src="ess.png" alt="Logo">
</div>
<div style="flex:1; text-align: center; color: white;">
    <h1><b>DMSC Integration Testing</b></h1>
</div>
<div style="flex:1; text-align:right; color: white;">
    <h3>Last updated: """
    html += datetime.now().strftime("%B %d, %Y %I:%M %p")
    html += """</h3>
</div>
</div>
<div style="width: 100%; display: flex;">
    <div style="flex:1;">
    <br>
    Key: &nbsp;&nbsp;&nbsp;&nbsp; ✅=Passed &nbsp;&nbsp;&nbsp;&nbsp; ❌=Failed &nbsp;&nbsp;&nbsp;&nbsp; ⚠️=Skipped<br><br>
    <table style="width: 100%; border-collapse: collapse;">
        <tr>
            <th style="border: 1px solid black;">Test Name</th>
"""
    instruments = sorted(set(INSTRUMENTS) - {"none"})
    for instr in instruments:
        html += f'            <th style="border: 1px solid black;">{instr}</th>\n'
    html += "        </tr>\n"
    for group in GROUPS:
        html += f'        <tr>\n            <td colspan="{len(INSTRUMENTS)}" style="border: 1px solid black;"><b>{group}</b></td>\n'
        html += "        </tr>\n"
        for test_name, instr_map in test_map[group].items():
            html += f'        <tr>\n            <td style="border: 1px solid black;">{test_name}</td>\n'
            if "none" in instr_map:
                html += f'            <td colspan="{len(INSTRUMENTS)}" style="border: 1px solid black;">'
                for test in instr_map["none"]:
                    text, status, url = test
                    prefix = f"{text}: " if text else ""
                    html += f'{prefix}<a href="{url}" style="text-decoration:none;">{char_map[status]}</a><br>'
                html += "</td>\n"
            else:
                for ins in instruments:
                    if ins not in instr_map:
                        html += f'            <td style="border: 1px solid black;">{char_map["error"]}</td>\n'
                    else:
                        html += '            <td style="border: 1px solid black;">'
                        for test in instr_map[ins]:
                            text, status, url = test
                            # status, url = instr_map[ins]
                            prefix = f"{text}: " if text else ""
                            html += f'{prefix}<a href="{url}" style="text-decoration:none;">{char_map[status]}</a><br>'
                        html += "</td>\n"

            html += "        </tr>\n"
        html += f'        <tr>\n            <td colspan="{len(INSTRUMENTS)}" ">&nbsp;</td>\n        </tr>\n'
    html += """    </table>
</div>
"""

    # Add plotly chart with test history
    chart = """
<div style="flex: 1;">
    <div id="chart"></div>
</div>
<script>
"""
    chart += f"var pipeline_run_ids = {dates};\n"
    chart += f"var failing_test = {failing_test};\n"
    chart += f"var skipped_tests = {skipped_tests};\n"
    chart += f"var passing_tests = {passing_tests};\n"
    chart += """
var data = [
    {
        x: pipeline_run_ids,
        y: failing_test,
        type: 'scatter',
        mode: 'lines+markers',
        name: 'Failed Tests',
        marker: {color: 'red'}
    },
    {
        x: pipeline_run_ids,
        y: skipped_tests,
        type: 'scatter',
        mode: 'lines+markers',
        name: 'Skipped Tests',
        marker: {color: 'orange'}
    },
    {
        x: pipeline_run_ids,
        y: passing_tests,
        type: 'scatter',
        mode: 'lines+markers',
        name: 'Passed Tests',
        marker: {color: 'green'}
    }
];
var layout = {
    title: 'Test History',
    xaxis: {title: 'Pipeline Run ID'},
    yaxis: {title: 'Number of Tests'}
};
Plotly.newPlot('chart', data, layout);
</script>
"""
    html += chart

    html += """
</div>
</body>
</html>"""
    return html


def main():
    pipeline, last_50 = get_pipelines(DMSC_NIGHTLY_PROJECT_ID)
    pipeline_id = pipeline["id"]
    # pipeline_id = datetime.fromisoformat(pipeline["updated_at"].replace("Z", "+00:00"))
    jobs = get_jobs(DMSC_NIGHTLY_PROJECT_ID, pipeline_id)

    success, failed, others = [], [], []
    for job in jobs:
        # TODO: Map teams to jobs
        temp_teams = ", ".join(random.choices(TEAMS, k=2))
        job_obj = Job(
            job["web_url"], job["status"], job["name"], job["stage"], temp_teams
        )

        if job["status"] == "success":
            success.append(job_obj)
        elif job["status"] == "failed":
            failed.append(job_obj)
        else:
            job_obj.job_run_status = ""
            others.append(job_obj)

    all_jobs = success + failed + others
    for job in all_jobs:
        logging.info(
            f"Job: {job.job_name}, Status: {job.job_run_status}, URL: {job.job_run_url}, Stage: {job.job_stage}"
        )

    run_chart = []
    for pid, updated_at in last_50:
        test_report = get_test_report(DMSC_NIGHTLY_PROJECT_ID, pid)
        total_tests = test_report["total_count"]
        failed_tests = test_report["failed_count"]
        skipped_tests = test_report["skipped_count"]
        passed_tests = total_tests - failed_tests - skipped_tests
        failed_job_percentage = (
            (failed_tests / total_tests * 100) if total_tests else 0.0
        )
        run_chart.append(
            (
                pid,
                total_tests,
                failed_job_percentage,
                failed_tests,
                skipped_tests,
                passed_tests,
                updated_at,
            )
        )

    run_chart.reverse()
    # last_run_skipped_test
    last_run_test_report = get_test_report(DMSC_NIGHTLY_PROJECT_ID, pipeline_id)
    test_suites = last_run_test_report["test_suites"]
    skipped_test_suites = []
    for test in test_suites:
        job_name = test["name"]
        job_name_url = f"https://git.esss.dk/dmsc-nightly/dmsc-nightly/-/pipelines/{pipeline_id}/test_report?job_name={quote(job_name)}"
        for test_cases in test["test_cases"]:
            if test_cases["status"] == "skipped":
                skipped_test_suites.append(
                    (test_cases["classname"], test_cases["name"], job_name_url)
                )

    environment = Environment(loader=FileSystemLoader("templates/"))
    template = environment.get_template("dashboard.html")

    date = datetime.fromisoformat(pipeline["updated_at"].replace("Z", "+00:00"))
    formatted_date = date.strftime("%B %d, %Y %I:%M %p") + " UTC"

    percentage_data = [i[2] for i in run_chart]
    failed_job_percentage = f"{percentage_data[-1]:.2f}%"
    pipeline_run_ids = [i[0] for i in run_chart]
    number_of_tests = [i[1] for i in run_chart]
    failing_test = [i[3] for i in run_chart]
    skipped_tests = [i[4] for i in run_chart]
    passing_tests = [i[5] for i in run_chart]
    dates = [i[6] for i in run_chart]

    test_map = {group: {instr: {} for instr in INSTRUMENTS} for group in GROUPS}
    for test in test_suites:
        job_name = test["name"]
        job_name_url = f"https://git.esss.dk/dmsc-nightly/dmsc-nightly/-/pipelines/{pipeline_id}/test_report?job_name={quote(job_name)}"
        instr = "none"
        for ins in INSTRUMENTS:
            if ins in test["name"]:
                instr = ins
                break
        for test_cases in test["test_cases"]:
            for group in GROUPS:
                if f".{group}." in test_cases["classname"]:
                    name = test_cases["name"].replace("test_", "")
                    test_map[group][instr][name] = (
                        test_cases["status"],
                        job_name_url,
                    )

    # Make an inventory of all tests
    global_map = {group: {} for group in GROUPS}
    for group in GROUPS:
        for instr in INSTRUMENTS:
            for test_name, (status, url) in test_map[group][instr].items():
                raw_name = test_name.replace(f"{instr}_", "").replace(f"_{instr}", "")
                parts = raw_name.split("[")
                name_root = parts[0]
                if len(parts) > 1:
                    subtest = parts[1].replace("]", "")
                else:
                    subtest = ""
                if name_root not in global_map[group]:
                    global_map[group][name_root] = {}
                if instr not in global_map[group][name_root]:
                    global_map[group][name_root][instr] = []
                global_map[group][name_root][instr].append((subtest, status, url))

    print("MAAAAAAAAAAAAAAP:", global_map)

    content = to_html(
        global_map,
        pipeline_run_ids=pipeline_run_ids,
        failing_test=failing_test,
        skipped_tests=skipped_tests,
        passing_tests=passing_tests,
        dates=dates,
    )

    # content = template.render(
    #     gitlab_tests=all_jobs,
    #     failed_tests=failed,
    #     failed_job_percentage=failed_job_percentage,
    #     pipeline_end_time=formatted_date,
    #     teams=TEAMS,
    #     failing_test=failing_test,
    #     pipeline_run_ids=pipeline_run_ids,
    #     skipped_tests=skipped_tests,
    #     number_of_tests=number_of_tests,
    #     passing_tests=passing_tests,
    #     pipeline_id=pipeline_id,
    #     skipped_test_suites=skipped_test_suites,
    # )

    filename = "render/rendered.html"
    with open(filename, mode="w", encoding="utf-8") as message:
        message.write(content)
        logging.info(f"... wrote {filename}")


if __name__ == "__main__":
    main()
