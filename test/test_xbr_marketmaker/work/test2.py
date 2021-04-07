import sys
import time
import pprint
import random
import binascii

from web3.providers.eth_tester import EthereumTesterProvider
from eth_account.account import Account

from web3 import Web3
from web3.contract import ConciseContract
from solc import compile_source



def compile_source_file(file_path):
   with open(file_path, 'r') as f:
      source = f.read()

   return compile_source(source)


def deploy_contract(w3, contract_interface):
    tx_hash = w3.eth.contract(
        abi=contract_interface['abi'],
        bytecode=contract_interface['bin']).deploy()

    address = w3.eth.getTransactionReceipt(tx_hash)['contractAddress']
    return address


def wait_for_receipt(w3, tx_hash, poll_interval):
   while True:
       tx_receipt = w3.eth.getTransactionReceipt(tx_hash)
       if tx_receipt:
         return tx_receipt
       time.sleep(poll_interval)


url = "http://127.0.0.1:8545"
#url = 'https://mainnet.infura.io/45b74283353748308dd758b22ba17c35'
w3 = Web3(Web3.HTTPProvider(url, request_kwargs={'timeout': 10}))
#w3 = Web3(EthereumTesterProvider())

w3.eth.enable_unaudited_features()

# https://eth-account.readthedocs.io/en/latest/eth_account.html#eth_account.account.Account
private_key = '0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d'
acct = Account.privateKeyToAccount(private_key)
acct.address
acct.privateKey

######

# https://ethereum.stackexchange.com/a/48485
# https://ethereum.stackexchange.com/questions/36319/how-to-perform-transact-on-contract-functions-on-remote-node
# https://ethereum.stackexchange.com/questions/33231/how-to-build-a-raw-transaction-to-interact-with-a-contract-with-web3-py

SC_XBR_MARKETREGISTRY = '0xC89Ce4735882C9F0f0FE26686c53074E09B0D550'

contract_source_path = 'contract.sol'
compiled_sol = compile_source_file('contract.sol')

contract_id, contract_interface = compiled_sol.popitem()


if SC_XBR_MARKETREGISTRY is None or w3.eth.getCode(SC_XBR_MARKETREGISTRY) == '0x':
    print('SC does not exist .. creating:')
    contract_ = w3.eth.contract(abi=contract_interface['abi'], bytecode=contract_interface['bin'])

    construct_txn = contract_.constructor().buildTransaction({
        'from': acct.address,
        'nonce': w3.eth.getTransactionCount(acct.address),
        'gas': 1728712,
        'gasPrice': w3.toWei('21', 'gwei')})

    signed = acct.signTransaction(construct_txn)

    txn_hash = w3.eth.sendRawTransaction(signed.rawTransaction)

    receipt = wait_for_receipt(w3, txn_hash, 1)
    print("Transaction receipt mined: \n")

    if w3.eth.getCode(receipt.contractAddress) == '0x':
        raise Exception('deployment failed')
    
    pprint.pprint(dict(receipt))
else:
    print('SC already exists')

store_var_contract = w3.eth.contract(
    address=SC_XBR_MARKETREGISTRY,
    abi=contract_interface['abi'],
)

# https://web3py.readthedocs.io/en/latest/contracts.html#web3.contract.ConciseContract
sc = ConciseContract(store_var_contract)


var = sc._myVar()
print('current value: {}'.format(var))

var = store_var_contract.functions.getVar().call()
print('current value: {}'.format(var))

gas_estimate = store_var_contract.functions.setVar(255).estimateGas()
print("Gas estimate to transact with setVar: {0}\n".format(gas_estimate))

if False:
    tx_hash = store_var_contract.functions.setVar(255).transact()
else:

    txn_def = {
        'from': acct.address,
        'nonce': w3.eth.getTransactionCount(acct.address),
        'gas': 1728712,
        'gasPrice': w3.toWei('21', 'gwei')
    }
    var = random.randint(0, 255)
    txn = store_var_contract.functions.setVar(var).buildTransaction(txn_def)
    signed = acct.signTransaction(txn)
    txn_hash = w3.eth.sendRawTransaction(signed.rawTransaction)
    print('set new value: {}'.format(var))

receipt = wait_for_receipt(w3, txn_hash, 1)
print("Transaction receipt mined: transactionHash=0x{} gasUsed={} blockNumber={}".format(binascii.b2a_hex(receipt.transactionHash).decode(), receipt.gasUsed, receipt.blockNumber))
#pprint.pprint(dict(receipt))
