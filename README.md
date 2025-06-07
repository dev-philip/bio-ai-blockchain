## Features

- **Claim Management**: Add and retrieve biological claims with associated metadata
- **Ownership Control**: Secure ownership transfer and management
- **Data Verification**: Cryptographic verification of claim data
- **Access Control**: Role-based access control for claim management

## Prerequisites

- [Rust](https://www.rust-lang.org/tools/install)
- [Solana CLI](https://docs.solana.com/cli/install-solana-cli-tools)
- [Anchor Framework](https://www.anchor-lang.com/docs/installation)
- [Node.js](https://nodejs.org/) (for testing)

#

## Program Structure

### Accounts

- `ProgramData`: Main program account storing:
  - Owner address
  - Pending owner (for ownership transfers)
  - Claims vector

### Instructions

1. `initialize(initial_owner: Option<Pubkey>)`
   - Initializes the program
   - Sets the initial owner (defaults to creator if not specified)

2. `add_claim(claim_id: String, json_url: String, data_hash: [u8; 32])`
   - Adds a new biological claim
   - Requires owner authorization
   - Prevents duplicate claims

3. `get_claims()`
   - Retrieves all claims
   - Requires owner authorization

4. `transfer_ownership(new_owner: Pubkey)`
   - Initiates ownership transfer
   - Requires current owner authorization

5. `accept_ownership()`
   - Accepts pending ownership transfer
   - Requires new owner authorization

6. `renounce_ownership()`
   - Renounces program ownership
   - Sets owner to default address

## Testing

Run the test suite:
```bash
anchor test
```

The test suite covers:
- Program initialization
- Claim management
- Ownership transfers
- Access control
- Error handling

## Usage Example

```typescript
// Initialize program with custom owner
await program.methods
  .initialize(myAddress)
  .accounts({
    programData: programDataPda,
    creator: creator.publicKey,
    systemProgram: SystemProgram.programId,
  })
  .signers([creator])
  .rpc();

// Add a claim
await program.methods
  .addClaim(
    "claim_id",
    "https://example.com/claim.json",
    dataHash
  )
  .accounts({
    programData: programDataPda,
    creator: owner.publicKey,
  })
  .signers([owner])
  .rpc();
```

## Security

- All operations require proper authorization
- Ownership transfers use a two-step process
- Claim data is verified using cryptographic hashes
- Duplicate claims are prevented