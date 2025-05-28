use anchor_lang::prelude::*;
use anchor_lang::solana_program::hash::hash;
use anchor_lang::solana_program::program::invoke_signed;

declare_id!("DV88SqFNjehQYUdgezSEYK5Hp4xgx54s7Na4jpmBYKJ9");

#[program]
pub mod bio_hack {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>, initial_owner: Option<Pubkey>) -> Result<()> {
        let program_data = &mut ctx.accounts.program_data;
        program_data.claims = vec![];
        program_data.owner = initial_owner.unwrap_or(*ctx.accounts.creator.key);
        program_data.pending_owner = None;
        Ok(())
    }

    pub fn transfer_ownership(ctx: Context<TransferOwnership>, new_owner: Pubkey) -> Result<()> {
        let program_data = &mut ctx.accounts.program_data;
        require!(
            program_data.owner == *ctx.accounts.owner.key,
            ErrorCode::Unauthorized
        );
        require!(new_owner != program_data.owner, ErrorCode::InvalidNewOwner);
        
        program_data.pending_owner = Some(new_owner);
        Ok(())
    }

    pub fn accept_ownership(ctx: Context<AcceptOwnership>) -> Result<()> {
        let program_data = &mut ctx.accounts.program_data;
        require!(
            program_data.pending_owner == Some(*ctx.accounts.new_owner.key),
            ErrorCode::NoPendingOwnershipTransfer
        );
        
        program_data.owner = *ctx.accounts.new_owner.key;
        program_data.pending_owner = None;
        Ok(())
    }

    pub fn renounce_ownership(ctx: Context<RenounceOwnership>) -> Result<()> {
        let program_data = &mut ctx.accounts.program_data;
        require!(
            program_data.owner == *ctx.accounts.owner.key,
            ErrorCode::Unauthorized
        );
        
        program_data.owner = Pubkey::default();
        program_data.pending_owner = None;
        Ok(())
    }

    pub fn add_claim(
        ctx: Context<AddClaim>,
        claim_id: String,
        json_url: String,
        data_hash: [u8; 32],
    ) -> Result<()> {
        require!(!claim_id.is_empty(), ErrorCode::InvalidClaimId);
        require!(!json_url.is_empty(), ErrorCode::InvalidJsonUrl);
        
        let program_data = &mut ctx.accounts.program_data;
        require!(
            program_data.owner == *ctx.accounts.creator.key,
            ErrorCode::Unauthorized
        );

        let hashed_claim_id = hash(claim_id.as_bytes()).to_bytes();
        
        require!(
            !program_data.claims.iter().any(|c| c.claim_id_hash == hashed_claim_id),
            ErrorCode::ClaimAlreadyExists
        );
        
        program_data.claims.push(Claim {
            claim_id_hash: hashed_claim_id,
            json_url,
            data_hash,
            creator: *ctx.accounts.creator.key,
            created_at: Clock::get()?.unix_timestamp,
        });
        Ok(())
    }

    pub fn get_claims(ctx: Context<GetClaims>) -> Result<Vec<Claim>> {
        let program_data = &ctx.accounts.program_data;
        require!(
            program_data.owner == *ctx.accounts.requester.key,
            ErrorCode::Unauthorized
        );
        Ok(program_data.claims.clone())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(
        init,
        payer = creator,
        space = 8 + 32 + 32 + 4 + 10000, // Space for program data, owner pubkey, pending_owner, and claims
        seeds = [b"program_data"],
        bump
    )]
    pub program_data: Account<'info, ProgramData>,
    #[account(mut)]
    pub creator: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct TransferOwnership<'info> {
    #[account(mut)]
    pub program_data: Account<'info, ProgramData>,
    #[account(mut)]
    pub owner: Signer<'info>,
}

#[derive(Accounts)]
pub struct AcceptOwnership<'info> {
    #[account(mut)]
    pub program_data: Account<'info, ProgramData>,
    #[account(mut)]
    pub new_owner: Signer<'info>,
}

#[derive(Accounts)]
pub struct RenounceOwnership<'info> {
    #[account(mut)]
    pub program_data: Account<'info, ProgramData>,
    #[account(mut)]
    pub owner: Signer<'info>,
}

#[derive(Accounts)]
pub struct AddClaim<'info> {
    #[account(mut)]
    pub program_data: Account<'info, ProgramData>,
    #[account(mut)]
    pub creator: Signer<'info>,
}

#[derive(Accounts)]
pub struct GetClaims<'info> {
    pub program_data: Account<'info, ProgramData>,
    #[account(mut)]
    pub requester: Signer<'info>,
}

#[account]
pub struct ProgramData {
    pub owner: Pubkey,
    pub pending_owner: Option<Pubkey>,
    pub claims: Vec<Claim>,
}

#[derive(AnchorSerialize, AnchorDeserialize, Clone)]
pub struct Claim {
    pub claim_id_hash: [u8; 32],
    pub json_url: String,
    pub data_hash: [u8; 32],
    pub creator: Pubkey,
    pub created_at: i64,
}

#[error_code]
pub enum ErrorCode {
    #[msg("Only the owner can perform this action")]
    Unauthorized,
    #[msg("Claim with this ID already exists")]
    ClaimAlreadyExists,
    #[msg("Claim ID cannot be empty")]
    InvalidClaimId,
    #[msg("JSON URL cannot be empty")]
    InvalidJsonUrl,
    #[msg("Invalid new owner address")]
    InvalidNewOwner,
    #[msg("No pending ownership transfer")]
    NoPendingOwnershipTransfer,
}