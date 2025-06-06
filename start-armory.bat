@echo off
set BTC_RPC_USER=bitcoinrpc
set BTC_RPC_PASS=armory_prod_secure_pass_2024
set RPC_ETH_URL=https://mainnet.infura.io/v3/your_infura_key

echo Starting Bitcoin Armory services...
docker-compose down --volumes --remove-orphans
docker-compose up --build -d

echo.
echo Services started. Checking status...
timeout /t 5
docker-compose ps

echo.
echo To view logs, run: docker-compose logs -f
echo To stop services, run: docker-compose down 