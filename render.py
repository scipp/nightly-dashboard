import os
import json
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
def get_pipelines(project_id, n=5):
    # TODO: Add pagination or control number of pipelines to fetch
    # url = f"{GITLAB_API_URL}/projects/{project_id}/pipelines?ref=main&source=schedule&per_page={n}"
    url = f"{GITLAB_API_URL}/projects/{project_id}/pipelines?ref=main&per_page={n}"
    logging.info(f"Fetching pipelines from URL: {url}")
    headers = {"Authorization": f"PRIVATE-TOKEN {TOKEN}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    pipelines = response.json()
    # latest_pipeline = pipelines[0]
    # Get the last n pipeline ids
    last_n_pipelines = {
        pipeline["id"]: {
            "updated_at": str(
                datetime.fromisoformat(pipeline["updated_at"].replace("Z", ""))
                + timedelta(hours=1)
            ),
            "test_report": get_test_report(DMSC_NIGHTLY_PROJECT_ID, pipeline["id"]),
        }
        for pipeline in pipelines  # [:n]
    }
    return last_n_pipelines
    # return latest_pipeline, last_n_pipelines


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


def load_template(name):
    return Path(__file__).resolve().parent.joinpath("templates", name).read_text()


def test_html(
    test_history,
    test_name,
    test_report,
):
    out_html = load_template("test.html")
    last_updated = datetime.now().strftime("%B %d, %Y %I:%M %p")

    test_results = ""
    for date, status, url in zip(
        test_history["date"], test_history["status"], test_history["url"]
    ):
        test_results += f'<tr><td class="{status}"><a href="{url}">{date}</a></td><td class="{status}"><a href="{url}">{status}</a></td></tr>\n'

    return out_html.format(
        last_updated=last_updated,
        test_results=test_results,
        test_name=test_name,
        test_report=test_report,
    )


def main_html(
    test_map,
    # failing_tests,
    # skipped_tests,
    # passing_tests,
    # dates,
    global_chart,
    groups_chart,
):
    out_html = load_template("main.html")
    last_updated = datetime.now().strftime("%B %d, %Y %I:%M %p")

    #     # Add plotly chart with test history
    #     plotly_script = f"historyChart({global_chart['date']}, {global_chart['failed']}, {global_chart['skipped']}, {global_chart['success']});"

    #     plotly_script += "var data_groups = [\n"
    #     for group, data in groups_chart.items():
    #         plotly_script += f"""
    #     {{
    #         x: {data["date"]},
    #         y: {data["percentage"]},
    #         type: 'scatter',
    #         mode: 'lines+markers',
    #         name: '{group}',
    #     }},
    # """
    #     plotly_script += "];\n"
    #     plotly_script += "groupsChart(data_groups);"

    #     return out_html.format(
    #         last_updated=last_updated, tests_table="", plotly_script=plotly_script
    #     )

    tests_table = """
<thead>
<tr class="tests-table-header">
    <th>Test Name</th>
"""
    instruments = sorted(set(INSTRUMENTS) - {"none"})
    for instr in instruments:
        tests_table += f"            <th>{instr}</th>\n"
    tests_table += f'        <tr></thead></tbody>\n            <td colspan="{len(INSTRUMENTS)}" class="row-gap">&nbsp;</td>\n        </tr>\n'
    for i, group in enumerate(GROUPS):
        tests_table += f'        <tr>\n            <td colspan="{len(INSTRUMENTS)}" class="group-header"><b>{group}</b></td>\n'
        tests_table += "        </tr>\n"
        for test_name, instr_map in test_map[group].items():
            instr_map = {
                instr: sorted(tests, key=lambda t: t[0])
                for instr, tests in instr_map.items()
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
                        tests_table += (
                            f'            <td colspan="{len(INSTRUMENTS)}"></td></tr>\n'
                        )
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
                            tests_table += "            <td></td>\n"
                        else:
                            if i >= len(instr_map[ins]):
                                tests_table += "            <td></td>\n"
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
        tests_table += (
            f'        <tr>\n            <td colspan="{len(INSTRUMENTS)}" class="row-gap">&nbsp;</td>\n        </tr>\n'
            * 2
        )
    tests_table += "</tbody>"

    # Add plotly chart with test history
    plotly_script = f"historyChart({global_chart['date']}, {global_chart['failed']}, {global_chart['skipped']}, {global_chart['success']});"

    plotly_script += "var data_groups = [\n"
    for group, data in groups_chart.items():
        plotly_script += f"""
    {{
        x: {data["date"]},
        y: {data["percentage"]},
        type: 'scatter',
        mode: 'lines+markers',
        name: '{group}',
    }},
"""
    plotly_script += "];\n"
    plotly_script += "groupsChart(data_groups);"

    return out_html.format(
        last_updated=last_updated, tests_table=tests_table, plotly_script=plotly_script
    )

    # Add plotly chart with test history
    plotly_script = f"historyChart({global_chart['date']}, {global_chart['failed']}, {global_chart['skipped']}, {global_chart['success']});"

    #     # Add plotly chart with test groups
    #     for group in GROUPS:
    #         plotly_script += (
    #             f"var group_{group.replace('-', '_')} = {groups_chart[group]};\n"
    #         )
    #     plotly_script += "var data_groups = [\n"
    #     for group in GROUPS:
    #         plotly_script += f"""
    #     {{
    #         x: {dates},
    #         y: group_{group.replace("-", "_")},
    #         type: 'scatter',
    #         mode: 'lines+markers',
    #         name: '{group}',
    #     }},
    # """
    #     plotly_script += "];\n"
    #     plotly_script += "groupsChart(data_groups);"

    return main_html.format(
        last_updated=last_updated, tests_table=tests_table, plotly_script=plotly_script
    )


def _make_chart_container():
    return {key: [] for key in ("date", "success", "failed", "skipped")}


@dataclass
class Test:
    job_url: str
    status: str
    suite_name: str
    test_name: str
    output: str
    group: str
    classname: str
    raw_name: str = ""
    subtest: str = ""
    name_root: str = ""
    instrument: str = "none"


def main():
    # pipelines = get_pipelines(DMSC_NIGHTLY_PROJECT_ID)

    with open("render/pipelines.json", "r", encoding="utf-8") as f:
        pipelines = json.load(f)

    # print(pipelines)

    latest_pipeline = next(iter(pipelines))

    # pipeline_id = pipeline["id"]
    # jobs = get_jobs(DMSC_NIGHTLY_PROJECT_ID, pipeline_id)

    global_chart = _make_chart_container()
    groups_chart = {group: _make_chart_container() for group in GROUPS}

    # json.dump(
    #     pipelines,
    #     open("render/pipelines.json", "w", encoding="utf-8"),
    #     indent=4,
    #     ensure_ascii=False,
    # )

    tests_history = {}

    all_tests = {}

    for pid, pline in pipelines.items():
        global_chart["date"].append(pline["updated_at"])
        report = pline["test_report"]
        global_chart["success"].append(report["success_count"])
        global_chart["failed"].append(report["failed_count"] + report["error_count"])
        global_chart["skipped"].append(report["skipped_count"])

        for group in GROUPS:
            groups_chart[group]["date"].append(pline["updated_at"])
            groups_chart[group]["success"].append(0)
            groups_chart[group]["failed"].append(0)
            groups_chart[group]["skipped"].append(0)

        for suite in report["test_suites"]:
            for group in GROUPS:
                if group in suite["name"]:
                    test_group = group
                    break

            groups_chart[test_group]["success"][-1] += suite["success_count"]
            groups_chart[test_group]["failed"][-1] += (
                suite["failed_count"] + suite["error_count"]
            )
            groups_chart[test_group]["skipped"][-1] += suite["skipped_count"]

            for test in suite["test_cases"]:
                # print(test["classname"], test["classname"].split(".")[1])
                test_obj = Test(
                    job_url=f"https://git.esss.dk/dmsc-nightly/dmsc-nightly/-/pipelines/{pid}/test_report?job_name={quote(suite['name'])}",
                    status=test["status"],
                    suite_name=suite["name"],
                    test_name=test["name"],
                    output=str(test["system_output"]).replace("\n", "<br>"),
                    group=test_group,
                    classname=(
                        test["name"]
                        if len(test["classname"]) == 0
                        else test["classname"]
                    ).split(".")[1],
                )
                raw_name = test_obj.test_name.replace("test_", "")
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
                test_obj.raw_name = raw_name
                test_obj.subtest = subtest
                test_obj.name_root = name_root
                for instr in INSTRUMENTS:
                    if instr in test_obj.suite_name:
                        test_obj.instrument = instr

                unique_name = f"{test_obj.classname}|{test_obj.instrument}|{test_obj.name_root}|{test_obj.subtest}"
                if unique_name not in all_tests:
                    all_tests[unique_name] = []
                all_tests[unique_name].append(test_obj)

                if unique_name not in tests_history:
                    tests_history[unique_name] = {"date": [], "status": [], "url": []}
                tests_history[unique_name]["date"].append(pline["updated_at"])
                tests_history[unique_name]["status"].append(test_obj.status)
                tests_history[unique_name]["url"].append(test_obj.job_url)

    # print([(t.suite_name, t.test_name) for t in all_tests])

    for name, test in tests_history.items():
        content = test_html(
            test_history=test,
            test_name=name,
            test_report=all_tests[name][0].output,
        )

        filename = f"render/{name.replace("|", "_")}.html"
        with open(filename, mode="w", encoding="utf-8") as message:
            message.write(content)
            # logging.info(f"... wrote {filename}")

    table_map = {group: {} for group in GROUPS}
    for name, history in all_tests.items():
        test = history[0]  # Use the first test as representative
        if test.group not in table_map:
            table_map[test.group] = {}
        name_root = test.name_root.replace(f"{test.instrument}_", "")
        if name_root not in table_map[test.group]:
            table_map[test.group][name_root] = {}
        if test.instrument not in table_map[test.group][name_root]:
            table_map[test.group][name_root][test.instrument] = []
        filename = f"{name.replace("|", "_")}.html"
        table_map[test.group][name_root][test.instrument].append(
            (test.subtest, test.status, filename)
        )

    # Compute percentage of success for each group
    for data in groups_chart.values():
        perc = []
        for i in range(len(data["success"])):
            total = data["success"][i] + data["failed"][i]
            perc.append((data["success"][i] / total * 100) if total > 0 else 0.0)
        data["percentage"] = perc

    content = main_html(
        table_map,
        global_chart=global_chart,
        # failing_tests=failing_tests,
        # skipped_tests=skipped_tests,
        # passing_tests=passing_tests,
        # dates=dates,
        groups_chart=groups_chart,
    )

    filename = "render/index.html"
    with open(filename, mode="w", encoding="utf-8") as message:
        message.write(content)
        logging.info(f"... wrote {filename}")

    return

    # for job in jobs:
    #     job_obj = Job(
    #         job_run_url=job["web_url"],
    #         job_run_status=job["status"],
    #         job_name=job["name"],
    #     )

    #     if job["status"] == "success":
    #         success.append(job_obj)
    #     elif job["status"] == "failed":
    #         failed.append(job_obj)
    #     else:
    #         job_obj.job_run_status = ""
    #         others.append(job_obj)

    # all_jobs = success + failed + others
    # for job in all_jobs:
    #     logging.info(
    #         f"Job: {job.job_name}, Status: {job.job_run_status}, URL: {job.job_run_url}"
    #     )

    run_chart = []
    groups_chart = {group: [(0, 0) for _ in range(len(last_50))] for group in GROUPS}

    pipelines = {}

    for i, (pid, updated_at) in enumerate(last_50):
        test_report = get_test_report(DMSC_NIGHTLY_PROJECT_ID, pid)
        # print("========================================================")
        # print(f"Pipeline ID: {pid}, Updated at: {updated_at}")
        # print(test_report)
        # print(get_jobs(DMSC_NIGHTLY_PROJECT_ID, pid))
        pipelines[pid] = {
            "test_report": test_report,
            "updated_at": updated_at,
            # "jobs": get_jobs(DMSC_NIGHTLY_PROJECT_ID, pid),
        }
        # print([t["name"] for t in test_report["test_suites"]])
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

    json.dump(
        pipelines,
        open("render/pipelines.json", "w", encoding="utf-8"),
        indent=4,
        ensure_ascii=False,
    )

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
