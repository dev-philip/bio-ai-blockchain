use anchor_lang::prelude::*;

declare_id!("DV88SqFNjehQYUdgezSEYK5Hp4xgx54s7Na4jpmBYKJ9");

#[program]
pub mod bio_hack {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        let program_data = &mut ctx.accounts.program_data;
        program_data.organizations = vec![];
        Ok(())
    }

    pub fn create_organization(ctx: Context<CreateOrganization>, name: String) -> Result<()> {
        require!(!name.is_empty(), ErrorCode::InvalidOrganizationName);
        let program_data = &mut ctx.accounts.program_data;
        require!(
            !program_data.organizations.iter().any(|org| org.name == name),
            ErrorCode::OrganizationAlreadyExists
        );
        
        program_data.organizations.push(Organization {
            creator: *ctx.accounts.creator.key,
            name,
            members: vec![*ctx.accounts.creator.key], // Creator is first member
            claims: vec![],
        });
        Ok(())
    }

    pub fn add_member(
        ctx: Context<AddMember>,
        organization_name: String,
        new_member: Pubkey,
    ) -> Result<()> {
        let program_data = &mut ctx.accounts.program_data;
        let organization = program_data.organizations
            .iter_mut()
            .find(|org| org.name == organization_name)
            .ok_or(ErrorCode::OrganizationNotFound)?;

        require!(
            organization.members.contains(ctx.accounts.creator.key),
            ErrorCode::Unauthorized
        );
        require!(
            !organization.members.contains(&new_member),
            ErrorCode::MemberAlreadyExists
        );
        organization.members.push(new_member);
        Ok(())
    }

    pub fn add_claim(
        ctx: Context<AddClaim>,
        organization_name: String,
        claim_id: String,
        json_url: String,
        data_hash: [u8; 32],
    ) -> Result<()> {
        let program_data = &mut ctx.accounts.program_data;
        let organization = program_data.organizations
            .iter_mut()
            .find(|org| org.name == organization_name)
            .ok_or(ErrorCode::OrganizationNotFound)?;

        require!(
            organization.members.contains(ctx.accounts.creator.key),
            ErrorCode::Unauthorized
        );
        require!(
            !organization.claims.iter().any(|c| c.claim_id == claim_id),
            ErrorCode::ClaimAlreadyExists
        );
        
        organization.claims.push(Claim {
            claim_id,
            json_url,
            data_hash,
            creator: *ctx.accounts.creator.key,
            created_at: Clock::get()?.unix_timestamp,
        });
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(
        init,
        payer = creator,
        space = 8 + 4 + 10000, // Space for program data and organizations
        seeds = [b"program_data"],
        bump
    )]
    pub program_data: Account<'info, ProgramData>,
    #[account(mut)]
    pub creator: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct CreateOrganization<'info> {
    #[account(mut)]
    pub program_data: Account<'info, ProgramData>,
    #[account(mut)]
    pub creator: Signer<'info>,
}

#[derive(Accounts)]
pub struct AddMember<'info> {
    #[account(mut)]
    pub program_data: Account<'info, ProgramData>,
    #[account(mut)]
    pub creator: Signer<'info>,
}

#[derive(Accounts)]
pub struct AddClaim<'info> {
    #[account(mut)]
    pub program_data: Account<'info, ProgramData>,
    #[account(mut)]
    pub creator: Signer<'info>,
}

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

#[error_code]
pub enum ErrorCode {
    #[msg("Only organization members can perform this action")]
    Unauthorized,
    #[msg("Member already exists in the organization")]
    MemberAlreadyExists,
    #[msg("Claim with this ID already exists")]
    ClaimAlreadyExists,
    #[msg("Organization not found")]
    OrganizationNotFound,
    #[msg("Organization with this name already exists")]
    OrganizationAlreadyExists,
    #[msg("Organization name cannot be empty")]
    InvalidOrganizationName,
}