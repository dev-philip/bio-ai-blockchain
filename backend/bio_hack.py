import os
import json
from pathlib import Path
from dotenv import load_dotenv
from solana_fork.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from anchorpy import Program, Provider, Wallet, Idl, Context
from typing import List, Optional
import hashlib
import anchorpy

# Verify anchorpy version
print(f"Using anchorpy version: {anchorpy.__version__}")
if anchorpy.__version__ != "0.23.2":
    raise ImportError(
        f"Expected anchorpy-fork version 0.23.2, but found {anchorpy.__version__}. "
        "Please uninstall anchorpy and install anchorpy-fork with: "
        "pip uninstall anchorpy -y && pip install anchorpy-fork==0.23.2"
    )

# Load environment variables
load_dotenv()

class BioHackClient:
    def __init__(self):
        """Initialize the BioHackClient with Solana devnet and program details."""
        print("Initializing BioHackClient...")
        
        # Load environment variables
        self.program_id = Pubkey.from_string(
            os.getenv('PROGRAM_ID', 'DV88SqFNjehQYUdgezSEYK5Hp4xgx54s7Na4jpmBYKJ9')
        )
        self.network = os.getenv('NETWORK', 'devnet')
        self.rpc_url = os.getenv('RPC_URL', 'https://api.devnet.solana.com')
        self.wallet_path = os.path.expanduser(os.getenv('WALLET_PATH', '~/.config/solana/id.json'))
        
        # Validate environment variables
        if not os.path.exists(self.wallet_path):
            print(f"Wallet file not found at {self.wallet_path}")
            raise FileNotFoundError(f"Wallet file not found at {self.wallet_path}")
        
        print(f"Program ID: {self.program_id}")
        print(f"Network: {self.network}")
        print(f"RPC URL: {self.rpc_url}")
        print(f"Wallet path: {self.wallet_path}")
        
        # Load wallet
        try:
            with open(self.wallet_path) as f:
                keypair_data = json.load(f)
                self.keypair = Keypair.from_bytes(bytes(keypair_data))
            print(f"Wallet loaded successfully. Public key: {self.keypair.pubkey()}")
        except Exception as e:
            print(f"Error loading wallet: {e}")
            raise
        
        # Setup client and provider
        self.client = AsyncClient(self.rpc_url)
        self.wallet = Wallet()
        self.provider = Provider(self.client, self.w_keypair)
        
        try:
            idl_path = './bio_hack.json'
            print(f"Loading IDL from: {idl_path}")
            with open(idl_path) as f:
                idl_json = json.load(f)
            
            # Validate IDL structure
            required_fields = ["instructions", "accounts", "types"]
            missing_fields = [field for field in required_fields if field not in idl_json]
            if missing_fields:
                print(f"IDL missing required fields: {missing_fields}")
                raise ValueError(f"IDL missing required fields: {missing_fields}")
            
            # Patch IDL: Remove 'discriminator' from accounts as a fallback for AnchorPy compatibility
            if "accounts" in idl_json:
                for account in idl_json["accounts"]:
                    if "discriminator" in account:
                        del account["discriminator"]
                        print(f"Removed 'discriminator' from account: {account['name']} to ensure compatibility")
            
            # Log the modified accounts section for debugging
            print("Modified IDL accounts section:", json.dumps(idl_json.get("accounts"), []))
            
            # Parse IDL
            try:
                idl = Idl.from_json(json.dumps(idl_json))
                self.program = Program(idl, self.program_id, self.provider)
                print("Program initialized successfully")
            except Exception as e:
                print(f"Failed to parse IDL: {e}")
                print("Regenerate IDL with: anchor build && cp target/idl/bio_hack.json ./bio_hack.json")
                print("Check https://github.com/chainlink-anchorpy or https://github.com/kevinheavey/chainlink-anchorpy for issues")
                raise
        except Exception as e:
            print(f"Error loading IDL: {e}")
            raise

    async def initialize(self, initial_owner: Optional[Pubkey] = None) -> bool:
        """Initialize the program data account with optional initial owner."""
        try:
            print("\nInitializing program...")
            # Find PDA for program data
            [program_data_pda, _] = Pubkey.find_program_address(
                [b"program_data"],
                self.program_id
            )
            print(f"Program data PDA: {program_data_pda}")
            
            # Call initialize instruction
            tx = await self.program.rpc["initialize"](
                initial_owner,
                ctx=Context(
                    accounts={
                        "program_data": program_data_pda,
                        "creator": self.keypair.pubkey(),
                        "system_program": Pubkey.from_string("11111111111111111111111111111111"),
                    }
                )
            )
            print(f"Program initialized! Transaction: {tx}")
            return True
        except Exception as e:
            error_msg = str(e)
            if "6000" in error_msg:
                print("Error: Unauthorized - Only the owner can perform this action")
            else:
                print(f"Error initializing program: {e}")
            return False

    async def transfer_ownership(self, new_owner: Pubkey) -> bool:
        """Transfer ownership to a new address."""
        try:
            print(f"\nTransferring ownership to: {new_owner}")
            # Find PDA for program data
            [program_data_pda, _] = Pubkey.find_program_address(
                [b"program_data"],
                self.program_id
            )
            print(f"Program data PDA: {program_data_pda}")
            
            # Call transfer_ownership instruction
            tx = await self.program.rpc["transfer_ownership"](
                new_owner,
                ctx=Context(
                    accounts={
                        "program_data": program_data_pda,
                        "owner": self.keypair.pubkey(),
                    }
                )
            )
            print(f"Ownership transfer initiated! Transaction: {tx}")
            return True
        except Exception as e:
            error_msg = str(e)
            if "6000" in error_msg:
                print("Error: Unauthorized - Only the owner can perform this action")
            elif "6004" in error_msg:
                print("Error: Invalid new owner address")
            else:
                print(f"Error transferring ownership: {e}")
            return False

    async def accept_ownership(self) -> bool:
        """Accept pending ownership transfer."""
        try:
            print("\nAccepting ownership transfer...")
            # Find PDA for program data
            [program_data_pda, _] = Pubkey.find_program_address(
                [b"program_data"],
                self.program_id
            )
            print(f"Program data PDA: {program_data_pda}")
            
            # Call accept_ownership instruction
            tx = await self.program.rpc["accept_ownership"](
                ctx=Context(
                    accounts={
                        "program_data": program_data_pda,
                        "new_owner": self.keypair.pubkey(),
                    }
                )
            )
            print(f"Ownership accepted! Transaction: {tx}")
            return True
        except Exception as e:
            error_msg = str(e)
            if "6005" in error_msg:
                print("Error: No pending ownership transfer")
            else:
                print(f"Error accepting ownership: {e}")
            return False

    async def renounce_ownership(self) -> bool:
        """Renounce ownership of the program."""
        try:
            print("\nRenouncing ownership...")
            # Find PDA for program data
            [program_data_pda, _] = Pubkey.find_program_address(
                [b"program_data"],
                self.program_id
            )
            print(f"Program data PDA: {program_data_pda}")
            
            # Call renounce_ownership instruction
            tx = await self.program.rpc["renounce_ownership"](
                ctx=Context(
                    accounts={
                        "program_data": program_data_pda,
                        "owner": self.keypair.pubkey(),
                    }
                )
            )
            print(f"Ownership renounced! Transaction: {tx}")
            return True
        except Exception as e:
            error_msg = str(e)
            if "6000" in error_msg:
                print("Error: Unauthorized - Only the owner can perform this action")
            else:
                print(f"Error renouncing ownership: {e}")
            return False

    async def get_owner(self) -> Optional[Pubkey]:
        """Get the current owner of the program."""
        try:
            print("\nGetting program owner...")
            # Find PDA for program data
            [program_data_pda, _] = Pubkey.find_program_address(
                [b"program_data"],
                self.program_id
            )
            print(f"Program data PDA: {program_data_pda}")
            
            # Fetch the ProgramData account
            account_data = await self.program.account["ProgramData"].fetch(program_data_pda)
            print(f"Current owner: {account_data.owner}")
            print(f"Pending owner: {account_data.pending_owner}")
            return account_data.owner
        except Exception as e:
            print(f"Error getting owner: {e}")
            return None

    async def add_claim(self, claim_id: str, json_url: str, data_hash: bytes) -> bool:
        """Add a new claim to the program."""
        try:
            print(f"\nAdding claim: {claim_id}")
            # Validate inputs
            if not claim_id:
                raise ValueError("Claim ID cannot be empty")
            if not json_url:
                raise ValueError("JSON URL cannot be empty")
            if len(data_hash) != 32:
                raise ValueError("Data hash must be 32 bytes")
            
            # Find PDA for program data
            [program_data_pda, _] = Pubkey.find_program_address(
                [b"program_data"],
                self.program_id
            )
            print(f"Program data PDA: {program_data_pda}")
            
            # Call add_claim instruction
            tx = await self.program.rpc["add_claim"](
                claim_id,
                json_url,
                list(data_hash),  # Convert bytes to list for Anchor
                ctx=Context(
                    accounts={
                        "program_data": program_data_pda,
                        "creator": self.keypair.pubkey(),
                    }
                )
            )
            print(f"Claim added! Transaction: {tx}")
            return True
        except Exception as e:
            error_msg = str(e)
            if "6000" in error_msg:
                print("Error: Unauthorized - Only the owner can perform this action")
            elif "6001" in error_msg:
                print("Error: Claim with this ID already exists")
            elif "6002" in error_msg:
                print("Error: Invalid Claim ID")
            elif "6003" in error_msg:
                print("Error: Invalid JSON URL")
            else:
                print(f"Error adding claim: {e}")
            return False

    async def get_claims(self) -> Optional[List[dict]]:
        """Retrieve all claims from the program."""
        try:
            print("\nGetting claims...")
            # Find PDA for program data
            [program_data_pda, _] = Pubkey.find_program_address(
                [b"program_data"],
                self.program_id
            )
            print(f"Program data PDA: {program_data_pda}")
            
            # Fetch the ProgramData account
            account_data = await self.program.account["ProgramData"].fetch(program_data_pda)
            claims = account_data.claims  # Access the claims vector
            print(f"Retrieved {len(claims)} claims")
            return [
                {
                    "claim_id_hash": claim.claim_id_hash,
                    "json_url": claim.json_url,
                    "data_hash": claim.data_hash,
                    "creator": str(claim.creator),
                    "created_at": claim.created_at
                } for claim in claims
            ]
        except Exception as e:
            print(f"Error getting claims: {e}")
            return None

    async def close(self):
        """Close the client connection."""
        print("\nClosing client connection...")
        await self.client.close()
        print("Client connection closed")

async def main():
    """Example usage of BioHackClient."""
    client = BioHackClient()
    
    try:
        # Initialize program with optional initial owner
        initial_owner = None  # Set this to a Pubkey if you want to specify an initial owner
        init_success = await client.initialize(initial_owner)
        if not init_success:
            print("Initialization failed, exiting...")
            return
        
        # Get current owner
        current_owner = await client.get_owner()
        if current_owner:
            print(f"Current owner: {current_owner}")
        
        # Example: Transfer ownership
        # new_owner = Pubkey.from_string("NEW_OWNER_PUBKEY")
        # transfer_success = await client.transfer_ownership(new_owner)
        
        # Example: Accept ownership (as new owner)
        # accept_success = await client.accept_ownership()
        
        # Example: Renounce ownership
        # renounce_success = await client.renounce_ownership()
        
        # Add a claim
        claim_id = "test_claim_1"
        json_url = "https://example.com/claim.json"
        data_hash = hashlib.sha256(b"example data").digest()
        add_success = await client.add_claim(claim_id, json_url, data_hash)
        if not add_success:
            print("Failed to add claim, continuing...")
        
        # Get all claims
        claims = await client.get_claims()
        if claims:
            print("Claims:", json.dumps(claims, indent=2))
        else:
            print("No claims retrieved or error occurred")
        
    finally:
        await client.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())