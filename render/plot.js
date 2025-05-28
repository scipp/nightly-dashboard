function historyChart(dates, failing_tests, skipped_tests, passing_tests) {
    var data = [
        {
            x: dates,
            y: failing_tests,
            type: 'scatter',
            mode: 'lines+markers',
            name: 'Failed Tests',
            marker: { color: 'red' }
        },
        {
            x: dates,
            y: skipped_tests,
            type: 'scatter',
            mode: 'lines+markers',
            name: 'Skipped Tests',
            marker: { color: 'orange' }
        },
        {
            x: dates,
            y: passing_tests,
            type: 'scatter',
            mode: 'lines+markers',
            name: 'Passed Tests',
            marker: { color: 'green' }
        }
    ];
    var layout = {
        title: {
            text: 'Test History',
        },
        yaxis: {
            title: {
                text: 'Number of Tests'
            }
        },
        showlegend: true,
        legend: {
            x: 1,
            y: 1,
            xanchor: 'right',
            yanchor: 'bottom',
            orientation: 'h',
        },
        paper_bgcolor: 'rgba(255,255,255, 0)',
        plot_bgcolor: 'rgba(255,255,255, 0)',
    };
    Plotly.newPlot('history_chart', data, layout);
}

function groupsChart(data_groups) {

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
        paper_bgcolor: 'rgba(255,255,255, 0)',
        plot_bgcolor: 'rgba(255,255,255, 0)',
    };
    Plotly.newPlot('groups_chart', data_groups, layout_groups);
}
