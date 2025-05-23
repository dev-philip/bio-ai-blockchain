# Bio-Hack

A Solana program for managing organizations, their members, and claims using a single program account.

## Program Overview

This program provides functionality to:
- Create organizations
- Manage organization membership
- Add claims to organizations
- Retrieve claims from organizations (members only)

## Deployment Information

- **Program ID**: `DV88SqFNjehQYUdgezSEYK5Hp4xgx54s7Na4jpmBYKJ9`
- **Network**: Solana Devnet
- **Explorer Links**:
  - [Program on Solana Explorer](https://explorer.solana.com/address/DV88SqFNjehQYUdgezSEYK5Hp4xgx54s7Na4jpmBYKJ9?cluster=devnet)
  - [Program Data Account](https://explorer.solana.com/address/F6u6fAKhhChncGSh5B8ZygM9197iwaEZcvXP6s3BDFWU?cluster=devnet)

## Program Structure

The program uses a single program account to store all data:

```rust
#[account]
pub struct ProgramData {
    pub organizations: Vec<Organization>,
}

#[derive(AnchorSerialize, AnchorDeserialize, Clone)]
pub struct Organization {
    pub creator: Pubkey,
    pub name: String,
    pub members: Vec<Pubkey>,
    pub claims: Vec<Claim>,
}

#[derive(AnchorSerialize, AnchorDeserialize, Clone)]
pub struct Claim {
    pub claim_id: String,
    pub json_url: String,
    pub data_hash: [u8; 32],
    pub creator: Pubkey,
    pub created_at: i64,
}
```

## Instructions

### Initialize Program
Initializes the program data account that will store all organizations and their data.

### Create Organization
Creates a new organization with the creator as the first member.

### Add Member
Allows existing organization members to add new members.

### Add Claim
Allows organization members to add claims to their organization.

### Get Claims
Retrieves all claims for an organization. Only organization members can access the claims.

## Error Handling

The program includes comprehensive error handling for various scenarios:
- Unauthorized access attempts
- Duplicate member additions
- Duplicate claim IDs
- Organization not found
- Duplicate organization names
- Invalid organization names

## Testing

The program includes extensive tests covering:
- Program initialization
- Organization creation and management
- Member management
- Claim management
- Error cases and edge conditions
- Claim retrieval authorization

## Security Considerations

- Member-based access control
- Unique member public keys
- Claim validation
- Organization name validation
- Protected claim retrieval

## Limitations

- No update functionality for organizations
- No deletion functionality
- No member removal functionality
- Fixed initial capacity for members and claims

## Future Improvements

- Add member removal functionality
- Implement different member roles
- Add claim update and deletion
- Add organization update functionality
- Implement dynamic capacity for members and claims
- Add pagination for claim retrieval
- Add claim filtering options

## Getting Started

1. Clone the repository
2. Install dependencies:
   ```bash
   yarn install
   ```
3. Build the program:
   ```bash
   anchor build
   ```
4. Run tests:
   ```bash
   anchor test
   ```

## Interacting with the Program

To interact with the deployed program on devnet:

1. Set up your Solana configuration:
   ```bash
   solana config set --url devnet
   ```

2. Get some devnet SOL:
   ```bash
   solana airdrop 2
   ```

3. Use the program ID in your client code:
   ```typescript
   const programId = new PublicKey("DV88SqFNjehQYUdgezSEYK5Hp4xgx54s7Na4jpmBYKJ9");
   ```

4. Example of retrieving claims:
   ```typescript
   const claims = await program.methods
     .getClaims(organizationName)
     .accounts({
       programData: programDataPDA,
       requester: wallet.publicKey,
     })
     .view();
   ```

## License

This project is licensed under the MIT License - see the LICENSE file for details.