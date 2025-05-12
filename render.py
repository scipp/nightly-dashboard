import os
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import requests

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


# API Functions
def get_pipelines(project_id):
    # TODO: Add pagination or control number of pipelines to fetch
    url = f"{GITLAB_API_URL}/projects/{project_id}/pipelines?ref=main&source=schedule&per_page=50"
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
    return response.json()


def load_main_template():
    return Path(__file__).resolve().parent.joinpath("templates", "main.html").read_text()


def to_html(
    test_map,
    failing_tests,
    skipped_tests,
    passing_tests,
    dates,
    groups_chart,
):
    main_html = load_main_template()
    last_updated = datetime.now().strftime("%B %d, %Y %I:%M %p")

    tests_table = """
<thead>
<tr class="tests-table-header">
    <th>Test Name</th>
"""
    instruments = sorted(set(INSTRUMENTS) - {"none"})
    for instr in instruments:
        tests_table += f'            <th>{instr}</th>\n'
    tests_table += f'        <tr></thead></tbody>\n            <td colspan="{len(INSTRUMENTS)}" class="row-gap">&nbsp;</td>\n        </tr>\n'
    for i, group in enumerate(GROUPS):
        tests_table += f'        <tr>\n            <td colspan="{len(INSTRUMENTS)}" class="group-header"><b>{group}</b></td>\n'
        tests_table += "        </tr>\n"
        for test_name, instr_map in test_map[group].items():
            instr_map = {
                instr: sorted(tests, key=lambda t: t[0]) for instr, tests in instr_map.items()
            }
            # Find max number of tests
            max_tests = 0
            for ins in INSTRUMENTS:
                if ins in instr_map:
                    max_tests = max(max_tests, len(instr_map[ins]))
            tests_table += f'        <tr>\n            <td rowspan="{max_tests}">{test_name.replace("_", " ")}</td>\n'
            if "none" in instr_map:
                for i in range(max_tests):
                    if i > 0:
                        tests_table += "        <tr>\n"
                    if i >= len(instr_map["none"]):
                        tests_table += f'            <td colspan="{len(INSTRUMENTS)}"></td></tr>\n'
                    else:
                        text, status, url = instr_map["none"][i]
                        if len(text) > 16:
                            text = text[:16] + "..."
                        if not text:
                            text = "&nbsp;"
                        tests_table += (
                            f'<td colspan="{len(INSTRUMENTS)}" class="{status}">'
                            f'<a href="{url}" style="text-decoration:none;display: block; width: 100%; height: 100%;">{text}</a></td></tr>\n'
                        )
            else:
                for i in range(max_tests):
                    if i > 0:
                        tests_table += "        <tr>\n"
                    for ins in instruments:
                        if ins not in instr_map:
                            tests_table += '            <td></td>\n'
                        else:
                            if i >= len(instr_map[ins]):
                                tests_table += '            <td></td>\n'
                            else:
                                text, status, url = instr_map[ins][i]
                                if len(text) > 16:
                                    text = text[:16] + "..."
                                if not text:
                                    text = "&nbsp;"
                                tests_table += (
                                    f'<td class="{status}">'
                                    f'<a href="{url}">{text}</a></td>\n'
                                )
                    tests_table += "        </tr>\n"
        tests_table += f'        <tr>\n            <td colspan="{len(INSTRUMENTS)}" class="row-gap">&nbsp;</td>\n        </tr>\n' * 2
    tests_table += '</tbody>'

    # Add plotly chart with test history
    plotly_script = f"historyChart({dates}, {failing_tests}, {skipped_tests}, {passing_tests});"
    # Add plotly chart with test groups
    for group in GROUPS:
        plotly_script += f"var group_{group.replace('-', '_')} = {groups_chart[group]};\n"
    plotly_script += "var data_groups = [\n"
    for group in GROUPS:
        plotly_script += f"""
    {{
        x: {dates},
        y: group_{group.replace("-", "_")},
        type: 'scatter',
        mode: 'lines+markers',
        name: '{group}',
    }},
"""
    plotly_script += "];\n"
    plotly_script += "groupsChart(data_groups);"

    return main_html.format(
        last_updated=last_updated,
        tests_table=tests_table,
        plotly_script=plotly_script
    )


def main():
    pipeline, last_50 = get_pipelines(DMSC_NIGHTLY_PROJECT_ID)
    pipeline_id = pipeline["id"]
    jobs = get_jobs(DMSC_NIGHTLY_PROJECT_ID, pipeline_id)

    success, failed, others = [], [], []
    for job in jobs:
        job_obj = Job(
            job_run_url=job["web_url"],
            job_run_status=job["status"],
            job_name=job["name"],
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
            f"Job: {job.job_name}, Status: {job.job_run_status}, URL: {job.job_run_url}"
        )

    run_chart = []
    groups_chart = {group: [(0, 0) for _ in range(len(last_50))] for group in GROUPS}
    for i, (pid, updated_at) in enumerate(last_50):
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

        # group_char should gather the percentage of success tests for each group
        for test_suite in test_report["test_suites"]:
            for test in test_suite["test_cases"]:
                for group in GROUPS:
                    if f".{group}." in test["classname"]:
                        ntot = groups_chart[group][i][0] + (test["status"] != "skipped")
                        nsuccess = groups_chart[group][i][1] + (
                            test["status"] == "success"
                        )
                        groups_chart[group][i] = (ntot, nsuccess)

    for group in GROUPS:
        groups_chart[group] = [
            (i[0], i[1] / i[0] * 100 if i[0] > 0 else 0.0) for i in groups_chart[group]
        ]
        groups_chart[group].reverse()

    run_chart.reverse()
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

    percentage_data = [i[2] for i in run_chart]
    failed_job_percentage = f"{percentage_data[-1]:.2f}%"
    failing_tests = [i[3] for i in run_chart]
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
                subtest = ""
                name_root = raw_name
                if "[" in raw_name:
                    parts = raw_name.split("[")
                    name_root = parts[0]
                    subtest = parts[1].replace("]", "")
                elif "__" in raw_name:
                    parts = raw_name.split("__")
                    name_root = parts[0]
                    subtest = parts[1]
                if name_root not in global_map[group]:
                    global_map[group][name_root] = {}
                if instr not in global_map[group][name_root]:
                    global_map[group][name_root][instr] = []
                global_map[group][name_root][instr].append((subtest, status, url))

    content = to_html(
        global_map,
        failing_tests=failing_tests,
        skipped_tests=skipped_tests,
        passing_tests=passing_tests,
        dates=dates,
        groups_chart=groups_chart,
    )

    filename = "render/rendered.html"
    with open(filename, mode="w", encoding="utf-8") as message:
        message.write(content)
        logging.info(f"... wrote {filename}")


if __name__ == "__main__":
    main()
