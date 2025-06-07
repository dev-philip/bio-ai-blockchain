import asyncio
import json
import os
from typing import Optional
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from anchorpy import Program, Provider, Wallet, Idl, Context

# Load IDL
IDL_PATH = "bio_hack.json"
with open(IDL_PATH, "r") as f:
    idl_data = json.load(f)

PROGRAM_ID = Pubkey(idl_data["address"])
PDA_SEED = b"program_data"

# Use default Solana CLI wallet or env override
DEFAULT_KEYPAIR_PATH = os.environ.get("SOLANA_WALLET", os.path.expanduser("~/.config/solana/id.json"))

print("🔥 File loaded") 

def load_wallet(path: str) -> Keypair:
    with open(path, "r") as f:
        secret = json.load(f)
    return Keypair.from_secret_key(bytes(secret))

async def get_provider() -> Provider:
    client = AsyncClient("https://api.devnet.solana.com")  # Change to mainnet-beta if needed
    wallet = Wallet(load_wallet(DEFAULT_KEYPAIR_PATH))
    return Provider(client, wallet)

async def get_program(provider: Provider) -> Program:
    idl = Idl.from_json(idl_data)
    return Program(idl, PROGRAM_ID, provider)

async def get_pda() -> Pubkey:
    return Pubkey.find_program_address([PDA_SEED], PROGRAM_ID)[0]

# ----------------- CONTRACT CALLS -----------------

async def initialize(initial_owner: Optional[str] = None):
    provider = await get_provider()
    program = await get_program(provider)
    pda = await get_pda()

    owner_pubkey = Pubkey(initial_owner) if initial_owner else None

    ctx = Context(accounts={
        "program_data": pda,
        "creator": provider.wallet.public_key,
        "system_program": Pubkey("11111111111111111111111111111111")
    })

    await program.rpc["initialize"](owner_pubkey, ctx=ctx)
    print("✅ Program initialized.")

async def accept_ownership():
    provider = await get_provider()
    program = await get_program(provider)
    pda = await get_pda()

    ctx = Context(accounts={
        "program_data": pda,
        "new_owner": provider.wallet.public_key
    })

    await program.rpc["accept_ownership"](ctx=ctx)
    print("✅ Ownership accepted.")

async def add_claim(claim_id: str, json_url: str, data_hash: bytes):
    print("adding claims....")
    provider = await get_provider()
    program = await get_program(provider)
    pda = await get_pda()

    ctx = Context(accounts={
        "program_data": pda,
        "creator": provider.wallet.public_key
    })

    await program.rpc["add_claim"](claim_id, json_url, list(data_hash), ctx=ctx)
    print("✅ Claim added.")

async def get_claims():
    provider = await get_provider()
    program = await get_program(provider)
    pda = await get_pda()

    ctx = Context(accounts={
        "program_data": pda,
        "requester": provider.wallet.public_key
    })

    claims = await program.rpc["get_claims"](ctx=ctx)
    print("📦 Claims:", claims)
    return claims

async def renounce_ownership():
    provider = await get_provider()
    program = await get_program(provider)
    pda = await get_pda()

    ctx = Context(accounts={
        "program_data": pda,
        "owner": provider.wallet.public_key
    })

    await program.rpc["renounce_ownership"](ctx=ctx)
    print("⚠️ Ownership renounced.")

async def transfer_ownership(new_owner: str):
    provider = await get_provider()
    program = await get_program(provider)
    pda = await get_pda()

    ctx = Context(accounts={
        "program_data": pda,
        "owner": provider.wallet.public_key
    })

    await program.rpc["transfer_ownership"](Pubkey(new_owner), ctx=ctx)
    print(f"🔄 Ownership transferred to {new_owner}")

# ----------------- MAIN (DEMO CALLS) -----------------
print("🔥 Top of file")

if __name__ == "__main__":
    print("✅ Running main")
    
    async def main():
        # Example: Initialize the program
        await initialize()
        
        # Example: Add a claim
        claim_id = "test_claim_1"
        json_url = "https://example.com/claim.json"
        data_hash = b"test_hash_data"
        await add_claim(claim_id, json_url, data_hash)
        
        # Example: Get all claims
        claims = await get_claims()
        print('claims', claims)
    
    # Run the async main function
    asyncio.run(main())


