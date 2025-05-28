import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import { BioHack } from "../target/types/bio_hack";
import { PublicKey, Keypair, SystemProgram } from "@solana/web3.js";
import { expect } from "chai";
import { BN } from "bn.js";

describe("bio-hack", () => {
  // Configure the client to use the local cluster
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);

  const program = anchor.workspace.BioHack as Program<BioHack>;
  
  // Test accounts
  const owner = Keypair.generate();
  const newOwner = Keypair.generate();
  const unauthorized = Keypair.generate();
  
  // Program data PDA
  const [programDataPda] = PublicKey.findProgramAddressSync(
    [Buffer.from("program_data")],
    program.programId
  );

  // Test data
  const testClaimId = "test_claim_1";
  const testJsonUrl = "https://example.com/claim.json";
  const testDataHash = Array(32).fill(1); // Example 32-byte hash as number array

  before(async () => {
    // Airdrop SOL to owner
    const signature = await provider.connection.requestAirdrop(
      owner.publicKey,
      2 * anchor.web3.LAMPORTS_PER_SOL
    );
    await provider.connection.confirmTransaction(signature);

    // Initialize program with owner
    await program.methods
      .initialize(owner.publicKey)
      .accounts({
        programData: programDataPda,
        creator: owner.publicKey,
        systemProgram: SystemProgram.programId,
      })
      .signers([owner])
      .rpc();

    // Verify initialization
    const programData = await program.account.programData.fetch(programDataPda);
    expect(programData.owner.toString()).to.equal(owner.publicKey.toString());
    expect(programData.claims.length).to.equal(0);
  });

  it("Adds and retrieves claims", async () => {
    // Add claim
    await program.methods
      .addClaim(testClaimId, testJsonUrl, testDataHash)
      .accounts({
        programData: programDataPda,
        creator: owner.publicKey,
      })
      .signers([owner])
      .rpc();

    // Get claims
    const programData = await program.account.programData.fetch(programDataPda);
    expect(programData.claims.length).to.equal(1);
    expect(programData.claims[0].jsonUrl).to.equal(testJsonUrl);
  });

  it("Prevents duplicate claims", async () => {
    try {
      // Try to add duplicate claim
      await program.methods
        .addClaim(testClaimId, testJsonUrl, testDataHash)
        .accounts({
          programData: programDataPda,
          creator: owner.publicKey,
        })
        .signers([owner])
        .rpc();
      expect.fail("Should have thrown an error");
    } catch (err) {
      expect(err.toString()).to.include("ClaimAlreadyExists");
    }
  });

  it("Prevents unauthorized operations", async () => {
    try {
      // Try to add claim with unauthorized account
      await program.methods
        .addClaim(testClaimId, testJsonUrl, testDataHash)
        .accounts({
          programData: programDataPda,
          creator: unauthorized.publicKey,
        })
        .signers([unauthorized])
        .rpc();
      expect.fail("Should have thrown an error");
    } catch (err) {
      expect(err.toString()).to.include("Unauthorized");
    }
  });

  it("Transfers ownership", async () => {
    // Initiate ownership transfer
    await program.methods
      .transferOwnership(newOwner.publicKey)
      .accounts({
        programData: programDataPda,
        owner: owner.publicKey,
      })
      .signers([owner])
      .rpc();

    // Verify pending owner
    let programData = await program.account.programData.fetch(programDataPda);
    expect(programData.pendingOwner.toString()).to.equal(newOwner.publicKey.toString());

    // Accept ownership
    await program.methods
      .acceptOwnership()
      .accounts({
        programData: programDataPda,
        newOwner: newOwner.publicKey,
      })
      .signers([newOwner])
      .rpc();

    // Verify new owner
    programData = await program.account.programData.fetch(programDataPda);
    expect(programData.owner.toString()).to.equal(newOwner.publicKey.toString());
    expect(programData.pendingOwner).to.be.null;
  });

  it("Renounces ownership", async () => {
    // Renounce ownership
    await program.methods
      .renounceOwnership()
      .accounts({
        programData: programDataPda,
        owner: newOwner.publicKey,
      })
      .signers([newOwner])
      .rpc();

    // Verify zero address owner
    const programData = await program.account.programData.fetch(programDataPda);
    expect(programData.owner.toString()).to.equal(PublicKey.default.toString());
  });
});