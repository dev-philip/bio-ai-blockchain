import asyncio
import json
import os
import time
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
from solders.transaction import VersionedTransaction
from solders.message import MessageV0
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TxOpts
from typing import List

# -------------------------------------------
# Config & Global Constants
# -------------------------------------------
PROGRAM_ID = Pubkey.from_string("DV88SqFNjehQYUdgezSEYK5Hp4xgx54s7Na4jpmBYKJ9")
PDA_SEED = b"program_data"
SYSTEM_PROGRAM = Pubkey.from_string("11111111111111111111111111111111")
DEFAULT_KEYPAIR_PATH = os.environ.get("SOLANA_WALLET", os.path.expanduser("~/.config/solana/id.json"))
RPC_ENDPOINT = os.environ.get("SOLANA_RPC", "https://api.devnet.solana.com")
MINIMUM_SOL = 0.000005
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# -------------------------------------------
# Wallet Loading Helpers
# -------------------------------------------

def load_wallet_from_secret(secret: list[int]) -> Keypair:
    try:
        return Keypair.from_bytes(bytes(secret))
    except Exception as e:
        raise ValueError(f"Failed to load wallet from secret: {e}")

def read_secret_key_from_file(path: str) -> list[int]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Secret key file not found: {path}")
    with open(path, "r") as f:
        data = f.read()
        try:
            secret = json.loads(data)
            if isinstance(secret, list) and all(isinstance(i, int) for i in secret):
                return secret
        except json.JSONDecodeError:
            import base58
            try:
                return list(base58.b58decode(data))
            except Exception as e:
                raise ValueError(f"Invalid secret key format: {e}")
    raise ValueError(f"Invalid secret key file: {path}")

def load_wallet() -> Keypair:
    try:
        secret = read_secret_key_from_file(DEFAULT_KEYPAIR_PATH)
        return load_wallet_from_secret(secret)
    except Exception as e:
        secret_b58 = os.environ.get("SOLANA_SECRET_KEY_B58")
        if secret_b58:
            import base58
            try:
                secret_bytes = base58.b58decode(secret_b58)
                return Keypair.from_bytes(secret_bytes)
            except Exception as e:
                raise RuntimeError(f"Failed to load wallet from base58 secret: {e}")
        raise RuntimeError(f"No valid wallet found: {e}")

# -------------------------------------------
# Helper Functions
# -------------------------------------------

def encode_option_pubkey(pubkey: Pubkey | None) -> bytes:
    """Encode an Option<Pubkey> as 1 byte (Some/None) + 32 bytes (if Some)."""
    if pubkey is None:
        return bytes([0])  # None
    return bytes([1]) + bytes(pubkey)  # Some + pubkey

def encode_string(s: str) -> bytes:
    """Encode a string as 4-byte length + UTF-8 bytes."""
    encoded = s.encode("utf-8")
    return len(encoded).to_bytes(4, "little") + encoded

def get_pda() -> Pubkey:
    """Derive the PDA for program_data."""
    pda, _ = Pubkey.find_program_address([PDA_SEED], PROGRAM_ID)
    return pda

# -------------------------------------------
# Instruction Construction
# -------------------------------------------

def build_initialize_instruction(creator: Pubkey, initial_owner: Pubkey | None) -> Instruction:
    """Build the initialize instruction."""
    program_data_pda = get_pda()
    discriminator = bytes([175, 175, 109, 31, 13, 152, 155, 237])
    data = discriminator + encode_option_pubkey(initial_owner)
    accounts: List[AccountMeta] = [
        AccountMeta(pubkey=program_data_pda, is_signer=False, is_writable=True),
        AccountMeta(pubkey=creator, is_signer=True, is_writable=True),
        AccountMeta(pubkey=SYSTEM_PROGRAM, is_signer=False, is_writable=False),
    ]
    return Instruction(PROGRAM_ID, data, accounts)

def build_add_claim_instruction(creator: Pubkey, claim_id: str, json_url: str, data_hash: bytes) -> Instruction:
    """Build the add_claim instruction."""
    program_data_pda = get_pda()
    discriminator = bytes([70, 114, 85, 106, 66, 244, 46, 99])
    if len(data_hash) != 32:
        raise ValueError("data_hash must be 32 bytes")
    data = discriminator + encode_string(claim_id) + encode_string(json_url) + data_hash
    accounts: List[AccountMeta] = [
        AccountMeta(pubkey=program_data_pda, is_signer=False, is_writable=True),
        AccountMeta(pubkey=creator, is_signer=True, is_writable=True),
    ]
    return Instruction(PROGRAM_ID, data, accounts)

def build_get_claims_instruction(requester: Pubkey) -> Instruction:
    """Build the get_claims instruction."""
    program_data_pda = get_pda()
    discriminator = bytes([137, 77, 151, 53, 39, 5, 110, 188])
    data = discriminator
    accounts: List[AccountMeta] = [
        AccountMeta(pubkey=program_data_pda, is_signer=False, is_writable=False),
        AccountMeta(pubkey=requester, is_signer=True, is_writable=True),
    ]
    return Instruction(PROGRAM_ID, data, accounts)

# -------------------------------------------
# Transaction Execution
# -------------------------------------------

async def initialize():
    print("🔧 Running initialize...")
    try:
        client = AsyncClient(RPC_ENDPOINT, commitment=Confirmed)
        if not await client.is_connected():
            raise ConnectionError(f"Failed to connect to RPC: {RPC_ENDPOINT}")
        print(f"Connected to RPC: {RPC_ENDPOINT}")

        wallet = load_wallet()
        creator = wallet.pubkey()
        print(f"Wallet public key: {creator}")

        balance_resp = await client.get_balance(creator)
        sol_balance = balance_resp.value / 1_000_000_000
        if sol_balance < MINIMUM_SOL:
            raise ValueError(f"Insufficient SOL balance: {sol_balance} SOL")
        print(f"Wallet balance: {sol_balance} SOL")

        initial_owner = creator
        instruction = build_initialize_instruction(creator, initial_owner)
        print(f"PDA: {get_pda()}")

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                blockhash_resp = await client.get_latest_blockhash()
                blockhash = blockhash_resp.value.blockhash
                print(f"Attempt {attempt}: Using blockhash {blockhash}")

                message = MessageV0.try_compile(
                    payer=creator,
                    instructions=[instruction],
                    address_lookup_table_accounts=[],
                    recent_blockhash=blockhash,
                )
                tx = VersionedTransaction(message, [wallet])

                opts = TxOpts(skip_confirmation=False, skip_preflight=True)
                tx_sig = await client.send_transaction(tx, opts=opts)
                print(f"✅ initialize() successful. Transaction Signature: {tx_sig.value}")
                return tx_sig.value

            except Exception as e:
                if "BlockhashNotFound" in str(e) and attempt < MAX_RETRIES:
                    print(f"Blockhash not found, retrying in {RETRY_DELAY} seconds...")
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                raise e

    except Exception as e:
        print(f"❌ initialize() failed: {e}")
        raise
    finally:
        await client.close()

async def add_claim(claim_id: str, json_url: str, data_hash: bytes):
    print("🔧 Running add_claim...")
    try:
        client = AsyncClient(RPC_ENDPOINT, commitment=Confirmed)
        if not await client.is_connected():
            raise ConnectionError(f"Failed to connect to RPC: {RPC_ENDPOINT}")
        print(f"Connected to RPC: {RPC_ENDPOINT}")

        wallet = load_wallet()
        creator = wallet.pubkey()
        print(f"Wallet public key: {creator}")

        balance_resp = await client.get_balance(creator)
        sol_balance = balance_resp.value / 1_000_000_000
        if sol_balance < MINIMUM_SOL:
            raise ValueError(f"Insufficient SOL balance: {sol_balance} SOL")
        print(f"Wallet balance: {sol_balance} SOL")

        instruction = build_add_claim_instruction(creator, claim_id, json_url, data_hash)
        print(f"PDA: {get_pda()}")

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                blockhash_resp = await client.get_latest_blockhash()
                blockhash = blockhash_resp.value.blockhash
                print(f"Attempt {attempt}: Using blockhash {blockhash}")

                message = MessageV0.try_compile(
                    payer=creator,
                    instructions=[instruction],
                    address_lookup_table_accounts=[],
                    recent_blockhash=blockhash,
                )
                tx = VersionedTransaction(message, [wallet])

                opts = TxOpts(skip_confirmation=False, skip_preflight=True)
                tx_sig = await client.send_transaction(tx, opts=opts)
                print(f"✅ add_claim() successful. Transaction Signature: {tx_sig.value}")
                return tx_sig.value

            except Exception as e:
                if "BlockhashNotFound" in str(e) and attempt < MAX_RETRIES:
                    print(f"Blockhash not found, retrying in {RETRY_DELAY} seconds...")
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                raise e

    except Exception as e:
        print(f"❌ add_claim() failed: {e}")
        raise
    finally:
        await client.close()

async def get_claims():
    print("🔧 Running get_claims...")
    try:
        client = AsyncClient(RPC_ENDPOINT, commitment=Confirmed)
        if not await client.is_connected():
            raise ConnectionError(f"Failed to connect to RPC: {RPC_ENDPOINT}")
        print(f"Connected to RPC: {RPC_ENDPOINT}")

        wallet = load_wallet()
        requester = wallet.pubkey()
        print(f"Wallet public key: {requester}")

        balance_resp = await client.get_balance(requester)
        sol_balance = balance_resp.value / 1_000_000_000
        if sol_balance < MINIMUM_SOL:
            raise ValueError(f"Insufficient SOL balance: {sol_balance} SOL")
        print(f"Wallet balance: {sol_balance} SOL")

        pda = get_pda()
        print(f"PDA: {pda}")

        # Check if PDA account exists and is initialized
        account_resp = await client.get_account_info(pda)
        if account_resp.value is None:
            print("PDA account not found. Initializing...")
            await initialize()
            return []  # Return empty list after initialization
        
        data = account_resp.value.data
        print(f"Raw PDA data length: {len(data)} bytes")
        print(f"Raw PDA data (hex): {data.hex()}")
        
        # Print data structure breakdown
        print("\nData Structure Breakdown:")
        print("------------------------")
        offset = 0
        print(f"0-7:    Program Discriminator: {data[offset:offset+8].hex()}")
        offset += 8
        print(f"8-39:   Owner: {Pubkey(data[offset:offset+32])}")
        offset += 32
        print(f"40-72:  Pending Owner: {'None' if data[offset] == 0 else Pubkey(data[offset+1:offset+33])}")
        offset += 33

        # Read number of claims (Anchor Vec length)
        if offset + 4 > len(data):
            print("Data too short for number of claims")
            await initialize()
            return []
        num_claims = int.from_bytes(data[offset:offset+4], "little")
        print(f"73-76:  Number of Claims: {num_claims}")
        offset += 4

        # Validate number of claims (should be reasonable)
        if num_claims > 1000:  # Arbitrary reasonable limit
            print(f"Invalid number of claims: {num_claims}")
            await initialize()
            return []

        claims = []
        for i in range(num_claims):
            print(f"\nProcessing claim {i+1}:")
            
            # Read claim_id_hash (32 bytes)
            if offset + 32 > len(data):
                print("Data too short for claim ID hash")
                break
            claim_id_hash = data[offset:offset+32]
            print(f"Claim ID hash: {claim_id_hash.hex()}")
            offset += 32

            # Read json_url (Anchor String)
            if offset + 4 > len(data):
                print("Data too short for JSON URL length")
                break
            json_url_len = int.from_bytes(data[offset:offset+4], "little")
            print(f"JSON URL length: {json_url_len}")
            offset += 4

            # Validate JSON URL length (should be reasonable)
            if json_url_len > 1000:  # Arbitrary reasonable limit
                print(f"Invalid JSON URL length: {json_url_len}")
                break

            if offset + json_url_len > len(data):
                print("Data too short for JSON URL")
                break
            try:
                json_url = data[offset:offset+json_url_len].decode("utf-8")
                print(f"JSON URL: {json_url}")
            except UnicodeDecodeError as e:
                print(f"Failed to decode JSON URL: {e}")
                print(f"Problematic bytes: {data[offset:offset+json_url_len].hex()}")
                print("Skipping malformed claim...")
                offset += json_url_len
                continue
            offset += json_url_len

            # Read data_hash (32 bytes)
            if offset + 32 > len(data):
                print("Data too short for data hash")
                break
            data_hash = data[offset:offset+32]
            offset += 32

            # Read creator (32 bytes)
            if offset + 32 > len(data):
                print("Data too short for creator")
                break
            creator = Pubkey(data[offset:offset+32])
            offset += 32

            # Read created_at (i64, 8 bytes)
            if offset + 8 > len(data):
                print("Data too short for created_at")
                break
            created_at = int.from_bytes(data[offset:offset+8], "little", signed=True)
            offset += 8

            claims.append({
                "claim_id_hash": claim_id_hash.hex(),
                "json_url": json_url,
                "data_hash": data_hash.hex(),
                "creator": str(creator),
                "created_at": created_at
            })

        print(f"Claims: {json.dumps(claims, indent=2)}")
        return claims

    except Exception as e:
        print(f"❌ get_claims() failed: {e}")
        raise
    finally:
        await client.close()

# -------------------------------------------
# Entry Point
# -------------------------------------------

async def main():
    print("🔥 Starting Solana program interaction")
    try:
        # First, initialize the PDA
        print("Initializing PDA...")
        await initialize()
        
        # Add a test claim
        claim_id = "claim_001"
        json_url = "https://example.com/claim.json"
        data_hash = bytes([0] * 32)  # Placeholder; use actual hash in production
        
        print("Adding test claim...")
        await add_claim(claim_id, json_url, data_hash)
        
        print("Retrieving claims...")
        claims = await get_claims()
        print(f"Retrieved claims: {json.dumps(claims, indent=2)}")
        
    except Exception as e:
        print(f"❌ Main execution failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())