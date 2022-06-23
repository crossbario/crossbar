import threading
from zlmdb import perf_counter_ns
from twisted.internet.task import react
from twisted.internet.defer import ensureDeferred
from twisted.internet.threads import deferToThread
import json
import treq
from web3 import Web3


async def get_blocknumber_treq(url):
    headers = {b'Content-Type': [b'application/json']}
    obj = {'jsonrpc': '2.0', 'id': 1, 'method': 'eth_blockNumber', 'params': []}
    data = json.dumps(obj, ensure_ascii=False, sort_keys=False, separators=(',', ':')).encode('utf8')

    response = await treq.post(url, data, headers=headers)
    obj = await treq.json_content(response)
    result = int(obj['result'], 0)

    return result


def _get_blocknumber_web3(w3):
    #print('_get_blocknumber_web3: thread {}'.format(threading.get_ident()))
    return w3.eth.blockNumber


def get_blocknumber_web3(reactor, w3):
    #print('get_blocknumber_web3: thread {}'.format(threading.get_ident()))
    return deferToThread(_get_blocknumber_web3, w3)


# our "real" main
async def _main(reactor):
    n = 10000
    url = "http://127.0.0.1:8545"
    #url = 'https://mainnet.infura.io/45b74283353748308dd758b22ba17c35'

    w3 = Web3(Web3.HTTPProvider(url, request_kwargs={'timeout': 10}))

    started = perf_counter_ns()
    for i in range(n):
        blocknumber = await get_blocknumber_treq(url)
        #print('blocknumber via treq: {}'.format(blocknumber))
    duration = float(perf_counter_ns() - started) / 10**9
    rps = float(n) / duration
    print('rps treq: {}'.format(rps))

    started = perf_counter_ns()
    for i in range(n):
        blocknumber = await get_blocknumber_web3(reactor, w3)
        #print('blocknumber via web3: {}'.format(blocknumber))
    duration = float(perf_counter_ns() - started) / 10**9
    rps = float(n) / duration
    print('rps web3/threads: {}'.format(rps))

    started = perf_counter_ns()
    for i in range(n):
        blocknumber = _get_blocknumber_web3(w3)
        #print('blocknumber via web3 (sync): {}'.format(blocknumber))
    duration = float(perf_counter_ns() - started) / 10**9
    rps = float(n) / duration
    print('rps web3/blocking: {}'.format(rps))


# a wrapper that calls ensureDeferred
def main():
    return react(
        lambda reactor: ensureDeferred(
            _main(reactor)
        )
    )


if __name__ == '__main__':
    main()
