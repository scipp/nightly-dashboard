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

function instrumentsChart(data_instruments) {

    var layout_instruments = {
        title: {
            text: 'Success Rate by Instrument',
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
    Plotly.newPlot('instruments_chart', data_instruments, layout_instruments);
}

if (new Date().getMonth() == 11) {

    const snowflakes = [];
    const maxSnowflakes = 250;
    let snowflakeCount = 0;

    function createSnowflake() {
        if (snowflakes.length >= maxSnowflakes) return;

        const snowflake = document.createElement('div');
        snowflake.classList.add('snowflake');

        // Every 1000th flake is a Santa 🎅
        snowflakeCount++;
        const isSanta = snowflakeCount % 1000 === 0;
        snowflake.textContent = isSanta ? '🎅' : '❄';
        snowflake.style.fontSize = isSanta
            ? '512px'
            : `${Math.random() * 10 + 10}px`;

        snowflake.style.left = `${Math.random() * window.innerWidth}px`;
        snowflake.style.top = '-20px';
        snowflake.style.opacity = isSanta ? 1 : Math.random();
        snowflake.dataset.speed = isSanta ? 1 : (Math.random() * 2 + 0.5);
        snowflake.dataset.isSanta = isSanta;

        document.body.appendChild(snowflake);
        snowflakes.push(snowflake);
    }

    function animateSnowflakes() {
        for (let i = snowflakes.length - 1; i >= 0; i--) {
            const snowflake = snowflakes[i];
            const speed = parseFloat(snowflake.dataset.speed);

            snowflake.style.top = `${parseFloat(snowflake.style.top) + speed}px`;

            const left = parseFloat(snowflake.style.left);
            snowflake.style.left = `${left + Math.sin(Date.now() / 1000 + i) * 0.5}px`;

            if (parseFloat(snowflake.style.top) > window.innerHeight + 50) {
                snowflake.remove();
                snowflakes.splice(i, 1);
            }
        }

        requestAnimationFrame(animateSnowflakes);
    }

    setInterval(createSnowflake, 100);

    animateSnowflakes();
}