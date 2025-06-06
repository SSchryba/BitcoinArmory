##Armory

**Created by Alan Reiner on 13 July, 2011**

[Armory](https://github.com/etotheipi/BitcoinArmory) is a full-featured Bitcoin client, offering a dozen innovative features not found in any other client software! Manage multiple wallets (deterministic and watching-only), print paper backups that work forever, import or sweep private keys, and keep your savings in a computer that never touches the internet, while still being able to manage incoming payments, and create outgoing payments with the help of a USB key.

Multi-signature transactions are accommodated under-the-hood about 80%, and will be completed and integrated into the UI soon.

**Armory has no independent networking components built in.** Instead, it relies on on the Satoshi client to securely connect to peers, validate blockchain data, and broadcast transactions for us.  Although it was initially planned to cut the umbilical cord to the Satoshi client and implement independent networking, it has turned out to be an inconvenience worth having. Reimplementing all the networking code would be fraught with bugs, security holes, and possible blockchain forking.  The reliance on Bitcoin-Qt right now is actually making Armory more secure!

##Donations

Please take a moment to donate! 1ArmoryXcfq7TnCSuZa9fQjRYwJ4bkRKfv

![bitcoin:1ArmoryXcfq7TnCSuZa9fQjRYwJ4bkRKfv][Donation Image]

##Building Armory From Source

See instructions [here][Armory Build Instructions]


##Dependencies

* GNU Compiler Collection  
 Linux:   Install package `g++`

* Crypto++  
 Linux:   Install package `libcrypto++-dev`  
 Windows: [Download][Windows Crypto Download]    
  
* SWIG  
 Linux:   Install package `swig`  
 Windows: [Download][Windows SWIG Download]  
 MSVS: Copy swigwin-2.x directory next to cryptopp as `swigwin`  
  
* Python 2.6/2.7  
 Linux:   Install package `python-dev`  
 Windows: [Download][Windows Python Download]  
  
* Python Twisted -- asynchronous networking  
 Linux:   Install package `python-twisted`  
 Windows: [Download][Windows Twisted Download]  
  
* PyQt 4 (for Python 2.X)  
 Linux:   Install packages `libqtcore4`, `libqt4-dev`, `python-qt4`, and `pyqt4-dev-tools`  
 Windows: [Download][Windows QT Download]  
  
* qt4reactor.py -- combined eventloop for PyQt and Twisted  
 All OS:  [Download][QT4 Reactor Download]  

* pywin32  
 Windows Only:  qt4reactor relies on pywin32 (for win32event module). [Download][Windows PyWin Download]  
  
* py2exe  
 (OPTIONAL - if you want to make a standalone executable in Windows)  
 Windows: [Download][Windows Py2Exe Download]  

##Sample Code

Armory contains over 25,000 lines of code, between the C++ and python libraries.  This can be very confusing for someone unfamiliar with the code (you).  Below I have attempted to illustrate the CONOPS (concept of operations) that the library was designed for, so you know how to use it in your own development activities.  There is a TON of sample code in the following:

* C++ -   [BlockUtilsTest.cpp](cppForSwig/BlockUtilsTest.cpp)
* Python -   [Unit Tests](pytest/), [sample_armory_code.py](extras/sample_armory_code.py)


##License

Distributed under the GNU Affero General Public License (AGPL v3)  
See [LICENSE file](LICENSE) or [here][License]

##Copyright

Copyright (C) 2011-2015, Armory Technologies, Inc.

## Docker & Docker Compose Usage

### Build and Run with Docker Compose

1. Build and start the services:
   ```sh
   docker-compose up --build
   ```
   This will start both the `bitcoind` and `armory-monitor` services.

2. Access Armory's RPC interface on port 8223 (or as configured).

3. To stop the services:
   ```sh
   docker-compose down
   ```

### Standalone Docker Build/Run

1. Build the Docker image:
   ```sh
   docker build -t armory-monitor .
   ```
2. Run the container:
   ```sh
   docker run -it --rm -p 8223:8223 armory-monitor
   ```

> **Note:**
> - The `docker-compose.yml` also runs a `bitcoind` service for blockchain backend. Adjust environment variables as needed for your setup.
> - Data is persisted in Docker volumes (`bitcoind_data`, `armory_data`).
> - For production, change the default RPC credentials in `docker-compose.yml`.

[Armory Build Instructions]: https://bitcoinarmory.com/building-from-source
[Windows Crypto Download]: http://www.cryptopp.com/#download
[Windows SWIG Download]: http://www.swig.org/download.html
[Windows Python Download]: http://www.python.org/getit/
[Windows Twisted Download]: http://twistedmatrix.com/trac/wiki/Downloads
[Windows QT Download]: http://www.riverbankcomputing.co.uk/software/pyqt/download
[QT4 Reactor Download]: https://launchpad.net/qt4reactor
[Windows PyWin Download]: http://sourceforge.net/projects/pywin32/files/pywin32/
[Windows Py2Exe Download]:  http://www.py2exe.org/
[License]: http://www.gnu.org/licenses/agpl.html
[Donation Image]: https://chart.googleapis.com/chart?chs=250x250&cht=qr&chl=bitcoin:1ArmoryXcfq7TnCSuZa9fQjRYwJ4bkRKfv?&label=Armory+Donation

# Bitcoin Armory Transaction Monitor

This module integrates with Bitcoin Armory to monitor and analyze both Bitcoin and Ethereum transactions. It provides real-time analytics and transaction monitoring without requiring private keys.

## Features

- Monitors Bitcoin transactions in real-time using Armory's BDM system
- Monitors Ethereum transactions using Web3
- Provides detailed transaction analytics for both chains
- Tracks active wallets and transaction volumes
- Integrates with Redis for analytics storage
- Uses environment variables for configuration
- Compatible with Armory's existing transaction handling system
- Supports both confirmed and pending transactions
- MEV (Maximal Extractable Value) monitoring for Ethereum
- No private keys required - read-only monitoring

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables (create a .env file):
```
# Bitcoin Configuration
RPC_BTC_URL=http://127.0.0.1:8332
RPC_BTC_USER=bitcoinrpc
RPC_BTC_PASS=yourpassword

# Ethereum Configuration
RPC_ETH_URL=https://mainnet.infura.io/v3/your_infura_key

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
```

3. Ensure Redis server is running on the configured host and port

## Usage

Run the transaction monitor:
```bash
python TransactionMonitor.py
```

The monitor will:
- Connect to your Bitcoin node via RPC
- Connect to Ethereum network via Web3
- Register with Armory's BDM for Bitcoin notifications
- Monitor transactions on both chains
- Analyze and store transaction data
- Track active wallets and volumes
- Log analytics to Redis

## Redis Analytics

The monitor stores various analytics in Redis:

### Bitcoin Analytics
- `faithswarm:btc_stats` - Hash containing:
  - active_wallets: Number of active Bitcoin wallets
  - total_transactions: Total transactions monitored
  - total_volume: Total transaction volume
  - last_update: Timestamp of last update
- `faithswarm:btc_analysis` - List of detailed transaction analyses including:
  - Transaction hash
  - Timestamp
  - Size
  - Input/output counts
  - Total output value
  - Involved addresses

### Ethereum Analytics
- `faithswarm:eth_stats` - Hash containing:
  - active_wallets: Number of active Ethereum wallets
  - total_transactions: Total transactions monitored
  - total_volume: Total transaction volume in ETH
  - last_update: Timestamp of last update
- `faithswarm:eth_analysis` - List of detailed transaction analyses including:
  - Transaction hash
  - From/To addresses
  - Value in ETH
  - Gas usage and price
  - Block number
  - Transaction status

### Error Logging
- `faithswarm:errors` - List of error messages (prefixed with "btc_error:" or "eth_error:")

## Security Notes

- No private keys required - read-only monitoring
- All sensitive data is stored in environment variables
- Redis should be properly secured in production
- Use a dedicated Ethereum node or trusted provider for production use
- Monitor has no ability to send transactions

## Integration with Armory

The TransactionMonitor class integrates with Armory's existing systems:
- Uses BDM for Bitcoin blockchain monitoring
- Handles both confirmed and zero-confirmation Bitcoin transactions
- Maintains compatibility with Armory's transaction handling
- Uses Armory's logging system for consistency
- Adds Ethereum monitoring capabilities while preserving Bitcoin functionality

## Error Handling

- All errors are logged to both Armory's logging system and Redis
- Network issues are handled gracefully with retries
- Connection status is verified on startup
- Separate error tracking for Bitcoin and Ethereum operations

## MEV Monitoring

The Ethereum monitoring includes MEV (Maximal Extractable Value) capabilities:
- Monitors pending transactions in the mempool
- Tracks both transaction senders and recipients
- Analyzes transaction patterns and volumes
- Provides insights into transaction timing and gas usage
- Maintains separate tracking for MEV-related transactions