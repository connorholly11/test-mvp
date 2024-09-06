function handleApiResponse(response) {
    if (response.status === 401) {
        window.location.href = '/login';
        throw new Error('Not authenticated');
    }
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
}

function updateBalance() {
    fetch('/api/account_summary')
        .then(handleApiResponse)
        .then(data => {
            console.log('Account summary:', data);
            if (data.error) {
                console.error('Error fetching account summary:', data.error);
                return;
            }
            document.getElementById('balance').textContent = '$' + (data.balance || 0).toFixed(2);
            document.getElementById('equity').textContent = '$' + (data.equity || 0).toFixed(2);
            document.getElementById('realized-pl').textContent = '$' + (data.realized_pl || 0).toFixed(2);
            document.getElementById('unrealized-pl').textContent = '$' + (data.unrealized_pl || 0).toFixed(2);
            document.getElementById('daily-pl').textContent = '$' + (data.daily_pl || 0).toFixed(2);
        })
        .catch(error => {
            console.error('Error updating balance:', error);
            document.getElementById('balance').textContent = 'Error';
            document.getElementById('equity').textContent = 'Error';
            document.getElementById('realized-pl').textContent = 'Error';
            document.getElementById('unrealized-pl').textContent = 'Error';
            document.getElementById('daily-pl').textContent = 'Error';
        });
}

function updatePositions() {
    fetch('/api/positions')
        .then(handleApiResponse)
        .then(data => {
            console.log('Positions:', data);
            const tbody = document.getElementById('positions-body');
            tbody.innerHTML = '';
            if (data.positions && Array.isArray(data.positions)) {
                data.positions.forEach(position => {
                    const row = tbody.insertRow();
                    row.insertCell(0).textContent = position.symbol;
                    row.insertCell(1).textContent = position.quantity;
                    row.insertCell(2).textContent = '$' + position.average_price.toFixed(2);
                    row.insertCell(3).textContent = '$' + position.current_value.toFixed(2);
                    row.insertCell(4).textContent = '$' + position.unrealized_pl.toFixed(2);
                });
                
                // Update position and average price in the trading section
                const positionQuantity = data.positions.length > 0 ? data.positions[0].quantity : 0;
                const avgPrice = data.positions.length > 0 ? data.positions[0].average_price : 0;
                document.getElementById('position-quantity').textContent = positionQuantity;
                document.getElementById('position-avg-price').textContent = '$' + avgPrice.toFixed(2);
            } else {
                console.error('Invalid positions data:', data);
            }
        })
        .catch(error => {
            console.error('Error updating positions:', error);
            document.getElementById('positions-body').innerHTML = '<tr><td colspan="5">Error loading positions</td></tr>';
        });
}

function updateMarketData() {
    fetch('/api/market_data')
        .then(handleApiResponse)
        .then(data => {
            console.log('Market data:', data);
            if (data.Close) {
                document.getElementById('mnq-price').textContent = parseFloat(data.Close).toFixed(2);
            } else if (data.Last) {
                document.getElementById('mnq-price').textContent = parseFloat(data.Last).toFixed(2);
            } else {
                document.getElementById('mnq-price').textContent = 'N/A';
            }
        })
        .catch(error => {
            console.error('Error updating market data:', error);
            document.getElementById('mnq-price').textContent = 'Error';
        });
}

function placeTrade(action) {
    const quantity = document.getElementById('quantity').value;
    const symbol = 'NQU24';  // Changed from '@NQU24' to 'NQU24'
    
    if (!quantity) {
        alert('Please enter a quantity');
        return;
    }

    console.log(`Placing trade: ${action} ${quantity} ${symbol}`);

    fetch('/api/trade', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ action, quantity: parseInt(quantity), symbol }),
    })
    .then(handleApiResponse)
    .then(data => {
        console.log('Trade response:', data);
        if (data.success) {
            alert(data.message);
            updateBalance();
            updatePositions();
        } else {
            alert(`Error: ${data.message}`);
        }
    })
    .catch(error => {
        console.error('Error placing trade:', error);
        alert(`Error placing trade: ${error.message}`);
    });
}

// Initial updates
updateBalance();
updatePositions();
updateMarketData();

// Set up intervals for updates
setInterval(updateBalance, 5000);  // Update balance every 5 seconds
setInterval(updatePositions, 5000);  // Update positions every 5 seconds
setInterval(updateMarketData, 1000);  // Update market data every second