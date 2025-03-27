import os
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
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


color_map = {
    "success": "rgba(0, 128, 0, 0.5)",
    "failed": "rgba(255, 0, 0, 0.5)",
    "skipped": "rgba(255, 165, 0, 0.5)",
    "error": "white",
}


def to_html(
    test_map,
    failing_test,
    skipped_tests,
    passing_tests,
    dates,
    groups_chart,
):
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="3600">
    <link rel="icon" href="favicon.ico" type="image/x-icon">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DMSC Integration Testing</title>
    <script src="https://cdn.plot.ly/plotly-3.0.1.min.js" charset="utf-8"></script>
</head>
<body style="font-family: Tahoma, sans-serif; border:0; margin:0;">
<div style="width: 100%; display: flex; height: 80px;">
<div style="flex:0.3;">
    <img src="https://ess.eu/themes/custom/ess/logo.svg" alt="Logo" height="80">
</div>
<div style="flex:1; text-align: center; color: white; background-color: #0094ca;">
    <h1><b>DMSC Integration Testing</b></h1>
</div>
<div style="flex:1; text-align:right; color: white; background-color: #0094ca;">
    <h3>Last updated: """
    html += datetime.now().strftime("%B %d, %Y %I:%M %p")
    html += """</h3>
</div>
</div>
<div style="width: 100%;">
    <table style="border-collapse: collapse;">
            <tr>
                <td style="width: 60%;vertical-align: top;">
    <br>
    """
    # Add colored rectangles for legend
    html += (
        f"Key: &nbsp;&nbsp;&nbsp;&nbsp; <div style='display:inline-block; width: 20px; height: 20px; background-color: {color_map['success']};'></div> "
        f"= Success &nbsp;&nbsp;&nbsp;&nbsp; <div style='display:inline-block; width: 20px; height: 20px; background-color: {color_map['failed']};'></div> "
        f"= Failed &nbsp;&nbsp;&nbsp;&nbsp; <div style='display:inline-block; width: 20px; height: 20px; background-color: {color_map['skipped']};'></div> = Skipped"
    )
    html += """<br><br>
    <table style="border-collapse: collapse;">
        <tr>
            <th style="border: 1px solid black;">Test Name</th>
"""
    instruments = sorted(set(INSTRUMENTS) - {"none"})
    for instr in instruments:
        html += f'            <th style="border: 1px solid black;">{instr}</th>\n'
    html += f'        <tr>\n            <td colspan="{len(INSTRUMENTS)}" ">&nbsp;</td>\n        </tr>\n'
    for i, group in enumerate(GROUPS):
        html += f'        <tr>\n            <td colspan="{len(INSTRUMENTS)}" style="border: 1px solid black;background-color: #D3D3D3;font-size: 1.5em;"><b>{group}</b></td>\n'
        html += "        </tr>\n"
        for test_name, instr_map in test_map[group].items():
            # Find max number of tests
            max_tests = 0
            for ins in INSTRUMENTS:
                if ins in instr_map:
                    max_tests = max(max_tests, len(instr_map[ins]))
            html += f'        <tr>\n            <td rowspan="{max_tests}" style="border: 1px solid black;">{test_name.replace("_", " ")}</td>\n'
            if "none" in instr_map:
                for i in range(max_tests):
                    if i > 0:
                        html += "        <tr>\n"
                    if i >= len(instr_map["none"]):
                        html += f'            <td colspan="{len(INSTRUMENTS)}" style="border: 1px solid black;"></td></tr>\n'
                    else:
                        text, status, url = instr_map["none"][i]
                        if len(text) > 16:
                            text = text[:16] + "..."
                        if not text:
                            text = "&nbsp;"
                        html += (
                            f'<td colspan="{len(INSTRUMENTS)}" style="border: 1px solid black; background-color: {color_map[status]};">'
                            f'<a href="{url}" style="text-decoration:none;display: block; width: 100%; height: 100%;">{text}</a></td></tr>\n'
                        )
            else:
                for i in range(max_tests):
                    if i > 0:
                        html += "        <tr>\n"
                    for ins in instruments:
                        if ins not in instr_map:
                            html += f'            <td style="border: 1px solid black; background-color: {color_map["error"]};"></td>\n'
                        else:
                            if i >= len(instr_map[ins]):
                                html += f'            <td style="border: 1px solid black; background-color: {color_map["error"]};"></td>\n'
                            else:
                                text, status, url = instr_map[ins][i]
                                if len(text) > 16:
                                    text = text[:16] + "..."
                                if not text:
                                    text = "&nbsp;"
                                html += (
                                    f'<td style="border: 1px solid black; background-color: {color_map[status]};">'
                                    f'<a href="{url}" style="text-decoration:none;display: block; width: 100%; height: 100%; color: black;">{text}</a></td>\n'
                                )
                    html += "        </tr>\n"
        html += f'        <tr>\n            <td colspan="{len(INSTRUMENTS)}" ">&nbsp;</td>\n        </tr>\n'
        html += f'        <tr>\n            <td colspan="{len(INSTRUMENTS)}" ">&nbsp;</td>\n        </tr>\n'
    html += """    </table>
</td>
<td style=" width: 40%; vertical-align: top;">
"""

    # Add plotly chart with test history
    chart = f"""
    <div id="chart"></div>
    <div id="groups_chart"></div>
</td>
</tr>
</table>
<script>
var dates = {dates};
var failing_test = {failing_test};
var skipped_tests = {skipped_tests};
var passing_tests = {passing_tests};
var data = [
    {{
        x: dates,
        y: failing_test,
        type: 'scatter',
        mode: 'lines+markers',
        name: 'Failed Tests',
        marker: {{color: 'red'}}
    }},
    {{
        x: dates,
        y: skipped_tests,
        type: 'scatter',
        mode: 'lines+markers',
        name: 'Skipped Tests',
        marker: {{color: 'orange'}}
    }},
    {{
        x: dates,
        y: passing_tests,
        type: 'scatter',
        mode: 'lines+markers',
        name: 'Passed Tests',
        marker: {{color: 'green'}}
    }}
];
var layout = {{
    title: {{
        text: 'Test History',
    }},
    yaxis: {{
        title: {{
            text: 'Number of Tests'
        }}
    }},
    showlegend: true,
    legend: {{
        x: 1,
        y: 1,
        xanchor: 'right',
        yanchor: 'bottom',
        orientation: 'h',
    }}
}};
Plotly.newPlot('chart', data, layout);
"""
    for group in GROUPS:
        chart += f"var group_{group.replace('-', '_')} = {groups_chart[group]};\n"
    chart += "var data_groups = [\n"
    for group in GROUPS:
        chart += f"""
    {{
        x: dates,
        y: group_{group.replace("-", "_")},
        type: 'scatter',
        mode: 'lines+markers',
        name: '{group}',
    }},
"""
    chart += "];\n"
    chart += """
var layout_groups = {
    title: {
        text: 'Success Rate by Group',
    },
    yaxis: {
        title: {
            text: 'Success Rate',
        },
        range: [0, 105],
    },
    showlegend: true,
    legend: {
        x: 1,
        y: -0.2,
        xanchor: 'right',
        yanchor: 'top',
        orientation: 'h',
    },
};
Plotly.newPlot('groups_chart', data_groups, layout_groups);
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
        failing_test=failing_test,
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
