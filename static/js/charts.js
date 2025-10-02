let chart;
let rawData;
let chartColors;

function initChart(data, colors) {
    rawData = data;
    chartColors = colors;
    
    const ctx = document.getElementById('validationChart').getContext('2d');
    
    // Initial aggregation with all locations
    const aggregated = aggregateData(rawData, null, null, null);
    
    // Calculate max value for consistent y-axis
    const maxValue = calculateMaxValue(rawData);
    
    chart = new Chart(ctx, {
        type: 'bar',
        data: aggregated,
        options: {
            responsive: true,
            maintainAspectRatio: true,
            animation: {
                duration: 600,
                easing: 'easeInOutQuart'
            },
            scales: {
                x: {
                    stacked: true,
                    title: {
                        display: true,
                        text: 'Period (Month)',
                        font: { size: 14, weight: 'bold' }
                    }
                },
                y: {
                    stacked: true,
                    title: {
                        display: true,
                        text: 'Record Count',
                        font: { size: 14, weight: 'bold' }
                    },
                    beginAtZero: true,
                    max: maxValue,
                    ticks: {
                        precision: 0
                    }
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'bottom'
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        footer: function(tooltipItems) {
                            let total = 0;
                            tooltipItems.forEach(item => {
                                total += item.parsed.y;
                            });
                            return 'Total: ' + total.toLocaleString();
                        }
                    }
                }
            }
        }
    });

    // Setup slicer buttons
    setupSlicers();
}

function aggregateData(data, selectedLocations, startDate, endDate) {
    // Filter data by locations and dates
    let filtered = data.filter(row => {
        const monthDate = row.month + '-01';
        const locationMatch = !selectedLocations || selectedLocations.length === 0 || selectedLocations.includes(row.location);
        const dateMatch = (!startDate || monthDate >= startDate) && (!endDate || monthDate <= endDate);
        return locationMatch && dateMatch;
    });
    
    // Get unique months and sort them
    const months = [...new Set(filtered.map(row => row.month))].sort();
    
    // Get unique variance categories
    const categories = [...new Set(filtered.map(row => row.variance_category))];
    
    // Aggregate counts by month and category
    const aggregated = {};
    categories.forEach(cat => {
        aggregated[cat] = {};
        months.forEach(month => {
            aggregated[cat][month] = 0;
        });
    });
    
    filtered.forEach(row => {
        aggregated[row.variance_category][row.month] += row.count;
    });
    
    // Build Chart.js dataset format
    const datasets = categories.map(category => ({
        label: category,
        data: months.map(month => aggregated[category][month]),
        backgroundColor: chartColors[category] || '#999999'
    }));
    
    return {
        labels: months,
        datasets: datasets
    };
}

function calculateMaxValue(data) {
    // Calculate the maximum stacked value across all months
    const monthTotals = {};
    
    data.forEach(row => {
        if (!monthTotals[row.month]) {
            monthTotals[row.month] = 0;
        }
        monthTotals[row.month] += row.count;
    });
    
    const maxTotal = Math.max(...Object.values(monthTotals));
    // Add 10% padding to the max value for visual breathing room
    return Math.ceil(maxTotal * 1.1);
}

function setupSlicers() {
    // Populate year slicer from data
    const years = [...new Set(rawData.map(row => row.month.substring(0, 4)))].sort();
    const yearSlicer = document.getElementById('year-slicer');
    years.forEach(year => {
        const btn = document.createElement('button');
        btn.className = 'slicer-btn active';
        btn.dataset.value = year;
        btn.textContent = year;
        yearSlicer.appendChild(btn);
    });
    
    // Add click handlers to all slicer buttons
    document.querySelectorAll('.slicer-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            this.classList.toggle('active');
            applyFilters();
        });
    });
}

function applyFilters() {
    // Get selected locations
    const selectedLocations = Array.from(document.querySelectorAll('#location-slicer .slicer-btn.active'))
        .map(btn => btn.dataset.value);
    
    // Get selected years
    const selectedYears = Array.from(document.querySelectorAll('#year-slicer .slicer-btn.active'))
        .map(btn => btn.dataset.value);
    
    // Get selected months
    const selectedMonths = Array.from(document.querySelectorAll('#month-slicer .slicer-btn.active'))
        .map(btn => btn.dataset.value);
    
    // Filter data
    let filtered = rawData.filter(row => {
        const year = row.month.substring(0, 4);
        const month = row.month.substring(5, 7);
        
        const locationMatch = selectedLocations.length === 0 || selectedLocations.includes(row.location);
        const yearMatch = selectedYears.length === 0 || selectedYears.includes(year);
        const monthMatch = selectedMonths.length === 0 || selectedMonths.includes(month);
        
        return locationMatch && yearMatch && monthMatch;
    });
    
    // Get unique months and sort them
    const months = [...new Set(filtered.map(row => row.month))].sort();
    
    // Get unique variance categories
    const categories = [...new Set(filtered.map(row => row.variance_category))];
    
    // Aggregate counts by month and category
    const aggregated = {};
    categories.forEach(cat => {
        aggregated[cat] = {};
        months.forEach(month => {
            aggregated[cat][month] = 0;
        });
    });
    
    filtered.forEach(row => {
        aggregated[row.variance_category][row.month] += row.count;
    });
    
    // Build datasets
    const datasets = categories.map(category => ({
        label: category,
        data: months.map(month => aggregated[category][month]),
        backgroundColor: chartColors[category] || '#999999'
    }));
    
    // Update labels
    chart.data.labels = months;
    
    // Update each dataset's data in place
    datasets.forEach((newDataset, index) => {
        if (chart.data.datasets[index]) {
            chart.data.datasets[index].data = newDataset.data;
        } else {
            chart.data.datasets.push(newDataset);
        }
    });
    
    // Remove excess datasets
    while (chart.data.datasets.length > datasets.length) {
        chart.data.datasets.pop();
    }
    
    // Smooth update
    chart.update('default');
}

