function updateBalance() {
    fetch('/api/account_summary')
        .then(response => response.json())
        .then(data => {
            console.log('Account summary:', data);
            document.getElementById('balance').textContent = '$' + data.balance.toFixed(2);
            document.getElementById('equity').textContent = '$' + data.equity.toFixed(2);
            document.getElementById('realized-pl').textContent = '$' + data.realized_pl.toFixed(2);
            document.getElementById('unrealized-pl').textContent = '$' + data.unrealized_pl.toFixed(2);
            document.getElementById('daily-pl').textContent = '$' + data.daily_pl.toFixed(2);
        })
        .catch(error => console.error('Error updating balance:', error));
}

function updatePositions() {
    fetch('/api/positions')
        .then(response => response.json())
        .then(data => {
            console.log('Positions:', data);
            const tbody = document.getElementById('positions-body');
            tbody.innerHTML = '';
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
        })
        .catch(error => console.error('Error updating positions:', error));
}

function updateMarketData() {
    fetch('/api/market_data')
        .then(response => response.json())
        .then(data => {
            console.log('Market data:', data);
            if (data.Close) {
                document.getElementById('mnq-price').textContent = parseFloat(data.Close).toFixed(2);
            }
        })
        .catch(error => console.error('Error updating market data:', error));
}

function placeTrade(action) {
    const quantity = document.getElementById('quantity').value;
    const symbol = '@NQU24';  // Add this line
    
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
        body: JSON.stringify({ action, quantity: parseInt(quantity), symbol }),  // Add symbol here
    })
    .then(response => response.json())
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