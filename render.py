import logging
import os
import pytz
from datetime import datetime, UTC
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import argparse
import requests

from bs4 import BeautifulSoup


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Constants
GITLAB_API_URL = "https://git.esss.dk/api/v4"
DMSC_NIGHTLY_PROJECT_ID = 301
TIMEZONE = pytz.timezone("Europe/Copenhagen")
TOKEN = os.getenv("GITLAB_PRIVATE_TOKEN")
INSTRUMENTS = [
    "beer",
    "bifrost",
    "dream",
    "estia",
    "loki",
    "magic",
    "nmx",
    "odin",
    "tbl",
    "heimdal",
    "freia",
    "skadi",
    "cspec",
    "miracles",
    "trex",
    "vespa",
    "none",
]
GROUPS = [
    "chexus",
    "nexusfiles-scipp",
    "ingestor",
    "nexusjsontemplate-tests",
    "scipp-analysis",
    "scitacean",
]


# API Functions
def get_pipelines(project_id, build_type, n):
    source_spec = "source=schedule&" if build_type == "nightly" else ""
    url = f"{GITLAB_API_URL}/projects/{project_id}/pipelines?{source_spec}per_page={n}"
    logging.info(f"Fetching pipelines from URL: {url}")
    headers = {"Authorization": f"PRIVATE-TOKEN {TOKEN}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    pipelines = response.json()
    # Get the last n pipeline ids
    last_n_pipelines = {
        pipeline["id"]: {
            "updated_at": datetime.fromisoformat(pipeline["updated_at"])
            .astimezone(tz=TIMEZONE)
            .strftime("%Y-%m-%d %H:%M:%S"),
            "test_report": get_test_report(DMSC_NIGHTLY_PROJECT_ID, pipeline["id"]),
        }
        for pipeline in pipelines
    }
    return last_n_pipelines


def get_test_report(project_id, pipeline_id):
    url = f"{GITLAB_API_URL}/projects/{project_id}/pipelines/{pipeline_id}/test_report"
    logging.info(f"Fetching test report for pipeline {pipeline_id} from URL: {url}")
    headers = {"Authorization": f"PRIVATE-TOKEN {TOKEN}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def get_job_list(project_id, pipeline_id):
    url = f"{GITLAB_API_URL}/projects/{project_id}/pipelines/{pipeline_id}/jobs?per_page=100"
    logging.info(f"Fetching job list for pipeline {pipeline_id} from URL: {url}")
    headers = {"Authorization": f"PRIVATE-TOKEN {TOKEN}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    job_list = response.json()
    return {job["name"]: job for job in job_list}


def load_template(name):
    return Path(__file__).resolve().parent.joinpath("templates", name).read_text()


def prettify_html(html_string):
    """Prettify HTML string using BeautifulSoup."""
    soup = BeautifulSoup(html_string, "html.parser")
    return soup.prettify(formatter="html")


def test_html(test_history, test_name, last_updated):
    out_html = load_template("test.html")

    colors = {
        "success": "var(--success-bg)",
        "success-new": "var(--success-new-bg)",
        "failed": "var(--failed-bg)",
        "failed-new": "var(--failed-new-bg)",
        "skipped": "var(--skipped-bg)",
        "error": "var(--failed-bg)",
    }

    test_results = ""
    for i, (date, url, status, report, pid) in enumerate(
        zip(
            test_history["date"],
            test_history["job_url"],
            test_history["status"],
            test_history["report"],
            test_history["pipeline_id"],
        )
    ):
        test_results += f"""<div class="tab">
    <input type="radio" id="tab-{i + 1}" name="tab-group-1"{" checked" if i == 0 else ""}>
    <label  style="color: {colors[status]};" for="tab-{i + 1}">{date} [<a href="https://git.esss.dk/dmsc-nightly/dmsc-nightly/-/pipelines/{pid}/builds">{pid}</a>]: {status}</label>
    <div class="content">
"""
        if url is not None:
            test_results += f"""
        <p style="color: #8ADEFF;"><b><u><a href="{url}" style="color: #8ADEFF;">View job log here</a></u></b></p>
        <hr>
"""
        test_results += f"""
        <p>{report}</p>
    </div>
</div>
"""

    return out_html.format(
        last_updated=last_updated,
        test_results=test_results,
        test_name=test_name,
    )


def main_html(
    test_map, global_chart, groups_chart, instruments_chart, build_type, last_updated
):
    out_html = load_template("main.html")

    tests_table = '<thead><tr class="tests-table-header"><th>Test Name</th>'

    instruments = sorted(set(INSTRUMENTS) - {"none"})
    for instr in instruments:
        tests_table += f"<th>{instr}</th>"
    tests_table += f'</tr></thead><tbody><tr><td colspan="{len(INSTRUMENTS)}" class="row-gap">&nbsp;</td></tr>'
    for i, group in enumerate(GROUPS):
        tests_table += f'<tr><td colspan="{len(INSTRUMENTS)}" class="group-header"><b>{group}</b></td>'
        tests_table += "</tr>"
        for test_name, instr_map in sorted(test_map[group].items()):
            instr_map = {
                instr: sorted(tests, key=lambda t: t[0])
                for instr, tests in instr_map.items()
            }
            # Find max number of tests
            max_tests = 0
            for ins in INSTRUMENTS:
                if ins in instr_map:
                    max_tests = max(max_tests, len(instr_map[ins]))
            tests_table += (
                f'<tr><td rowspan="{max_tests}">{test_name.replace("_", " ")}</td>'
            )
            if "none" in instr_map:
                for i in range(max_tests):
                    if i > 0:
                        tests_table += "<tr>"
                    if i >= len(instr_map["none"]):
                        tests_table += f'<td colspan="{len(INSTRUMENTS)}"></td></tr>'
                    else:
                        text, status, url = instr_map["none"][i]
                        if len(text) > 16:
                            text = text[:16] + "..."
                        if not text:
                            text = "&nbsp;"
                        tests_table += (
                            f'<td colspan="{len(INSTRUMENTS)}" class="{status}">'
                            f'<a href="{url}" style="text-decoration:none;display: block; width: 100%; height: 100%;">{text}</a></td></tr>'
                        )
            else:
                for i in range(max_tests):
                    if i > 0:
                        tests_table += "<tr>"
                    for ins in instruments:
                        if ins not in instr_map:
                            tests_table += "<td></td>"
                        else:
                            if i >= len(instr_map[ins]):
                                tests_table += "<td></td>"
                            else:
                                text, status, url = instr_map[ins][i]
                                if len(text) > 16:
                                    text = text[:16] + "..."
                                if not text:
                                    text = "&nbsp;"
                                tests_table += (
                                    f'<td class="{status}">'
                                    f'<a href="{url}">{text}</a></td>'
                                )
                    tests_table += "</tr>"
        tests_table += (
            f'<tr><td colspan="{len(INSTRUMENTS)}" class="row-gap">&nbsp;</td></tr>' * 2
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

    plotly_script += "var data_instruments = [\n"
    for instr, data in instruments_chart.items():
        plotly_script += f"""
    {{
        x: {data["date"]},
        y: {data["percentage"]},
        type: 'scatter',
        mode: 'lines+markers',
        name: '{instr}',
    }},
"""
    plotly_script += "];\n"
    plotly_script += "instrumentsChart(data_instruments);"

    return out_html.format(
        last_updated=last_updated,
        tests_table=tests_table,
        plotly_script=plotly_script,
        build_type=build_type,
        other_type="latest" if build_type == "nightly" else "nightly",
    )


def _get_overview_status(tests_history, key) -> str:
    ok = True
    found_at_least_one_test = False
    for name in tests_history.keys():
        if key in name:
            found_at_least_one_test = True
            if tests_history[name]["status"][0] != "success":
                ok = False
                break
    if found_at_least_one_test:
        return f"<td class='{'success' if ok else 'failed'}'></td>"
    else:
        return "<td class='notimplemented'></td>"


def overview_html(tests_history, last_updated):
    out_html = load_template("overview.html")

    processing_steps = [
        "NeXus written",
        "Scicat ingested",
        "NeXus file read",
        "Data reduced",
        "Reduced file read",
        "Analysis performed",
    ]

    overview_table = (
        '<thead><tr class="overview-table-header"><th>Instrument &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</th><th>'
        + "</th><th></th><th>".join(processing_steps)
        + '</th></tr></thead><tbody>'
    )

    instruments = sorted(set(INSTRUMENTS) - {"none"})
    for instr in instruments:
        overview_table += f"<tr><td>{instr.capitalize()}</td>"

        nexus_written = tests_history.get(
            f"ingestor|{instr}|file_found_is_not_old|manual"
        )
        if nexus_written is not None:
            overview_table += f"<td class='{nexus_written['status'][0]}'></td>"
        else:
            overview_table += "<td class='notimplemented'></td>"
        overview_table += "<td>></td>"

        ingested = tests_history.get(
            f"ingestor|{instr}|file_found_by_scicat_is_consistent_with_manual|"
        )
        if ingested is not None:
            overview_table += f"<td class='{ingested['status'][0]}'></td>"
        else:
            overview_table += "<td class='notimplemented'></td>"
        overview_table += "<td>></td>"

        # Nexus file read
        overview_table += _get_overview_status(
            tests_history, f"{instr}_read_detector_everything"
        )
        overview_table += "<td>></td>"

        # Data reduced
        overview_table += _get_overview_status(
            tests_history, f"{instr}|can_compute_wavelength"
        )
        overview_table += "<td>></td>"

        # Reduced file read
        overview_table += _get_overview_status(
            tests_history, f"{instr}|read_reduced_data"
        )
        overview_table += "<td>></td>"

        # Analysis performed
        overview_table += _get_overview_status(
            tests_history, f"{instr}|analyze_reduced_data"
        )

    overview_table += "</tbody>"

    return out_html.format(last_updated=last_updated, overview_table=overview_table)


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


def main(build_type, npipelines):
    now = datetime.now(UTC)
    last_updated = now.astimezone(tz=TIMEZONE).strftime("%B %d, %Y %H:%M:%S")

    pipelines = get_pipelines(
        DMSC_NIGHTLY_PROJECT_ID, build_type=build_type, n=npipelines
    )

    folder = Path("render") / build_type
    folder.mkdir(parents=True, exist_ok=True)

    global_chart = _make_chart_container()
    groups_chart = {group: _make_chart_container() for group in GROUPS}

    instrument_list = sorted(set(INSTRUMENTS) - {"none"})
    instruments_chart = {instr: _make_chart_container() for instr in instrument_list}

    tests_history = {}
    all_tests = {}

    for i, (pid, pline) in enumerate(pipelines.items()):
        job_list = get_job_list(DMSC_NIGHTLY_PROJECT_ID, pid)

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

        for instr in instrument_list:
            instruments_chart[instr]["date"].append(pline["updated_at"])
            instruments_chart[instr]["success"].append(0)
            instruments_chart[instr]["failed"].append(0)
            instruments_chart[instr]["skipped"].append(0)

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
                if test["classname"] is None:
                    continue

                classname = (
                    test["name"] if len(test["classname"]) == 0 else test["classname"]
                ).split(".")
                # Some test names and class names may be ill-formed (there is sometimes
                # a test with test name=internal, classname=pytest).
                classname = classname[int(len(classname) > 1)]

                test_obj = Test(
                    job_url=f"https://git.esss.dk/dmsc-nightly/dmsc-nightly/-/pipelines/{pid}/test_report?job_name={quote(suite['name'])}",
                    status=test["status"],
                    suite_name=suite["name"],
                    test_name=test["name"],
                    output=str(test["system_output"]).replace("\n", "<br>"),
                    group=test_group,
                    classname=classname,
                )
                raw_name = test_obj.test_name.replace("test_", "")
                subtest = ""
                name_root = raw_name
                if "__" in raw_name:
                    parts = raw_name.split("__")
                    name_root = parts[0].replace("[", "").replace("]", "")
                    subtest = parts[1].replace("[", "").replace("]", "")
                elif "[" in raw_name:
                    parts = raw_name.split("[")
                    name_root = parts[0]
                    subtest = parts[1].replace("]", "")
                test_obj.raw_name = raw_name
                test_obj.subtest = subtest
                test_obj.name_root = name_root
                for instr in INSTRUMENTS:
                    if instr in test_obj.suite_name:
                        test_obj.instrument = instr
                        break

                if test_obj.instrument != "none":
                    if test_obj.status == "success":
                        instruments_chart[test_obj.instrument]["success"][-1] += 1
                    elif test_obj.status == "skipped":
                        instruments_chart[test_obj.instrument]["skipped"][-1] += 1
                    else:
                        instruments_chart[test_obj.instrument]["failed"][-1] += 1

                unique_name = f"{test_obj.classname}|{test_obj.instrument}|{test_obj.name_root}|{test_obj.subtest}"
                if (i > 0) and (unique_name not in all_tests):
                    continue
                if unique_name not in all_tests:
                    all_tests[unique_name] = []
                all_tests[unique_name].append(test_obj)

                if unique_name not in tests_history:
                    tests_history[unique_name] = {
                        "date": [],
                        "status": [],
                        "url": [],
                        "report": [],
                        "job_url": [],
                        "pipeline_id": [],
                    }
                tests_history[unique_name]["date"].append(pline["updated_at"])
                tests_history[unique_name]["pipeline_id"].append(pid)
                if suite["name"] in job_list:
                    tests_history[unique_name]["job_url"].append(
                        job_list[suite["name"]]["web_url"]
                    )
                else:
                    tests_history[unique_name]["job_url"].append(None)
                tests_history[unique_name]["status"].append(test_obj.status)
                tests_history[unique_name]["url"].append(test_obj.job_url)
                tests_history[unique_name]["report"].append(test_obj.output)

    for name, test in tests_history.items():
        content = prettify_html(
            test_html(test_history=test, test_name=name, last_updated=last_updated)
        )

        filename = folder / f"{name.replace('|', '_')}.html"
        with open(filename, mode="w", encoding="utf-8") as message:
            message.write(content)
            logging.info(f"... wrote {filename}")

    recent_days = 7

    # Look at the test history: if the test has recently started failing, change status to 'failed-new'.
    for name, history in tests_history.items():
        if history["status"][0] == "failed":
            if len(history["status"]) >= recent_days and (
                not all(
                    status == "failed" for status in history["status"][:recent_days]
                )
            ):
                all_tests[name][0].status = "failed-new"

    # If the test has recently started succeeding, change status to 'success-new'.
    for name, history in tests_history.items():
        if history["status"][0] == "success":
            if not all(
                status == "success" for status in history["status"][:recent_days]
            ):
                all_tests[name][0].status = "success-new"

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
        filename = f"{name.replace('|', '_')}.html"
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

    # Compute percentage of success for each instrument
    for instr, data in instruments_chart.items():
        perc = []
        for i in range(len(data["success"])):
            total = data["success"][i] + data["failed"][i]
            perc.append((data["success"][i] / total * 100) if total > 0 else 0.0)
        data["percentage"] = perc

    content = prettify_html(
        main_html(
            table_map,
            global_chart=global_chart,
            groups_chart=groups_chart,
            instruments_chart=instruments_chart,
            build_type=build_type,
            last_updated=last_updated,
        )
    )

    filename = folder / "index.html"
    with open(filename, mode="w", encoding="utf-8") as message:
        message.write(content)
        logging.info(f"... wrote {filename}")

    # Write overview page
    content = prettify_html(overview_html(tests_history, last_updated=last_updated))
    filename = Path("render") / "overview.html"
    with open(filename, mode="w", encoding="utf-8") as message:
        message.write(content)
        logging.info(f"... wrote {filename}")

    return


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render the DMSC Nightly dashboard.")
    parser.add_argument(
        "build_type",
        choices=["nightly", "latest"],
        help="Type of dashboard to render: nightly or latest.",
    )
    parser.add_argument(
        "-n",
        "--number",
        type=int,
        default=50,
        help="Number of pipelines to fetch (default: 50).",
    )
    args = parser.parse_args()

    main(build_type=args.build_type, npipelines=args.number)
