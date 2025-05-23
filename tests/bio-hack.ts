import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import { BioHack } from "../target/types/bio_hack";
import { expect } from "chai";
import { PublicKey, SystemProgram } from "@solana/web3.js";

describe("bio-hack", () => {
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);

  const program = anchor.workspace.BioHack as Program<BioHack>;
  const wallet = provider.wallet;

  // Program data PDA
  const [programDataPDA] = PublicKey.findProgramAddressSync(
    [Buffer.from("program_data")],
    program.programId
  );

  // Test data
  const testOrgName = "TestOrg";
  const testClaimId = "claim-1";
  const testJsonUrl = "https://example.com/claim.json";
  const testDataHash = Array.from(new Uint8Array(32).fill(1)); // Convert to number array

  // Helper function to create a new wallet
  const createWallet = () => {
    return anchor.web3.Keypair.generate();
  };

  // Helper function to airdrop SOL to a wallet
  const airdrop = async (wallet: anchor.web3.Keypair, amount: number) => {
    const signature = await provider.connection.requestAirdrop(
      wallet.publicKey,
      amount * anchor.web3.LAMPORTS_PER_SOL
    );
    await provider.connection.confirmTransaction(signature);
  };

  describe("Program Initialization", () => {
    it("Initializes program data account", async () => {
      const tx = await program.methods
        .initialize()
        .accounts({
          programData: programDataPDA,
          creator: wallet.publicKey,
          systemProgram: SystemProgram.programId,
        })
        .rpc();

      console.log("Initialize transaction:", tx);
      const programData = await program.account.programData.fetch(programDataPDA);
      console.log("Program data after initialization:", programData);
      expect(programData.organizations).to.be.an("array").that.is.empty;
    });

    it("Fails to initialize program data account twice", async () => {
      try {
        await program.methods
          .initialize()
          .accounts({
            programData: programDataPDA,
            creator: wallet.publicKey,
            systemProgram: SystemProgram.programId,
          })
          .rpc();
        expect.fail("Should have thrown an error");
      } catch (err) {
        console.log("Expected error on second initialization:", err);
        expect(err).to.be.instanceOf(Error);
      }
    });
  });

  describe("Organization Management", () => {
    it("Creates organization successfully", async () => {
      const tx = await program.methods
        .createOrganization(testOrgName)
        .accounts({
          programData: programDataPDA,
          creator: wallet.publicKey,
        })
        .rpc();

      console.log("Create organization transaction:", tx);
      const programData = await program.account.programData.fetch(programDataPDA);
      console.log("Program data after organization creation:", programData);
      const org = programData.organizations[0];
      expect(org.name).to.equal(testOrgName);
      expect(org.creator.equals(wallet.publicKey)).to.be.true;
      expect(org.members).to.have.lengthOf(1);
      expect(org.members[0].equals(wallet.publicKey)).to.be.true;
      expect(org.claims).to.be.an("array").that.is.empty;
    });

    it("Fails to create organization with duplicate name", async () => {
      try {
        await program.methods
          .createOrganization(testOrgName)
          .accounts({
            programData: programDataPDA,
            creator: wallet.publicKey,
          })
          .rpc();
        expect.fail("Should have thrown an error");
      } catch (err) {
        console.log("Expected error on duplicate organization:", err);
        expect(err).to.be.instanceOf(Error);
      }
    });

    it("Fails to create organization with empty name", async () => {
      try {
        await program.methods
          .createOrganization("")
          .accounts({
            programData: programDataPDA,
            creator: wallet.publicKey,
          })
          .rpc();
        expect.fail("Should have thrown an error");
      } catch (err) {
        console.log("Expected error on empty organization name:", err);
        expect(err).to.be.instanceOf(Error);
      }
    });

    it("Creates multiple organizations successfully", async () => {
      const orgNames = ["Org1", "Org2", "Org3"];
      for (const name of orgNames) {
        const tx = await program.methods
          .createOrganization(name)
          .accounts({
            programData: programDataPDA,
            creator: wallet.publicKey,
          })
          .rpc();
        console.log(`Create organization ${name} transaction:`, tx);
      }

      const programData = await program.account.programData.fetch(programDataPDA);
      console.log("Program data after creating multiple organizations:", programData);
      console.log("Number of organizations:", programData.organizations.length);
      console.log("Organization names:", programData.organizations.map(org => org.name));
      expect(programData.organizations).to.have.lengthOf(4); // Including TestOrg
      expect(programData.organizations.map(org => org.name)).to.include.members(orgNames);
    });
  });

  describe("Member Management", () => {
    const newMember = createWallet();

    before(async () => {
      await airdrop(newMember, 1);
    });

    it("Adds member successfully", async () => {
      const tx = await program.methods
        .addMember(testOrgName, newMember.publicKey)
        .accounts({
          programData: programDataPDA,
          creator: wallet.publicKey,
        })
        .rpc();

      console.log("Add member transaction:", tx);
      const programData = await program.account.programData.fetch(programDataPDA);
      console.log("Program data after adding member:", programData);
      const org = programData.organizations.find(o => o.name === testOrgName);
      expect(org.members).to.have.lengthOf(2);
      expect(org.members[1].equals(newMember.publicKey)).to.be.true;
    });

    it("Fails to add duplicate member", async () => {
      try {
        await program.methods
          .addMember(testOrgName, newMember.publicKey)
          .accounts({
            programData: programDataPDA,
            creator: wallet.publicKey,
          })
          .rpc();
        expect.fail("Should have thrown an error");
      } catch (err) {
        console.log("Expected error on duplicate member:", err);
        expect(err).to.be.instanceOf(Error);
      }
    });

    it("Fails to add member to non-existent organization", async () => {
      try {
        await program.methods
          .addMember("NonExistentOrg", newMember.publicKey)
          .accounts({
            programData: programDataPDA,
            creator: wallet.publicKey,
          })
          .rpc();
        expect.fail("Should have thrown an error");
      } catch (err) {
        console.log("Expected error on non-existent organization:", err);
        expect(err).to.be.instanceOf(Error);
      }
    });

    it("Fails to add member when not a member", async () => {
      const nonMember = createWallet();
      await airdrop(nonMember, 1);

      try {
        await program.methods
          .addMember(testOrgName, newMember.publicKey)
          .accounts({
            programData: programDataPDA,
            creator: nonMember.publicKey,
          })
          .signers([nonMember])
          .rpc();
        expect.fail("Should have thrown an error");
      } catch (err) {
        console.log("Expected error on unauthorized member addition:", err);
        expect(err).to.be.instanceOf(Error);
      }
    });
  });

  describe("Claim Management", () => {
    it("Adds claim successfully", async () => {
      const tx = await program.methods
        .addClaim(testOrgName, testClaimId, testJsonUrl, testDataHash)
        .accounts({
          programData: programDataPDA,
          creator: wallet.publicKey,
        })
        .rpc();

      console.log("Add claim transaction:", tx);
      const programData = await program.account.programData.fetch(programDataPDA);
      console.log("Program data after adding claim:", programData);
      const org = programData.organizations.find(o => o.name === testOrgName);
      console.log("Organization claims:", org.claims);
      console.log("First claim:", org.claims[0]);
      console.log("Created at type:", typeof org.claims[0].createdAt);
      console.log("Created at value:", org.claims[0].createdAt);
      expect(org.claims).to.have.lengthOf(1);
      expect(org.claims[0].claimId).to.equal(testClaimId);
      expect(org.claims[0].jsonUrl).to.equal(testJsonUrl);
      expect(org.claims[0].dataHash).to.deep.equal(testDataHash);
      expect(org.claims[0].creator.equals(wallet.publicKey)).to.be.true;
      expect(org.claims[0].createdAt.toNumber()).to.be.a("number");
    });

    it("Fails to add claim with duplicate ID", async () => {
      try {
        await program.methods
          .addClaim(testOrgName, testClaimId, testJsonUrl, testDataHash)
          .accounts({
            programData: programDataPDA,
            creator: wallet.publicKey,
          })
          .rpc();
        expect.fail("Should have thrown an error");
      } catch (err) {
        console.log("Expected error on duplicate claim:", err);
        expect(err).to.be.instanceOf(Error);
      }
    });

    it("Fails to add claim to non-existent organization", async () => {
      try {
        await program.methods
          .addClaim("NonExistentOrg", testClaimId, testJsonUrl, testDataHash)
          .accounts({
            programData: programDataPDA,
            creator: wallet.publicKey,
          })
          .rpc();
        expect.fail("Should have thrown an error");
      } catch (err) {
        console.log("Expected error on non-existent organization:", err);
        expect(err).to.be.instanceOf(Error);
      }
    });

    it("Fails to add claim when not a member", async () => {
      const nonMember = createWallet();
      await airdrop(nonMember, 1);

      try {
        await program.methods
          .addClaim(testOrgName, "claim-2", testJsonUrl, testDataHash)
          .accounts({
            programData: programDataPDA,
            creator: nonMember.publicKey,
          })
          .signers([nonMember])
          .rpc();
        expect.fail("Should have thrown an error");
      } catch (err) {
        console.log("Expected error on unauthorized claim addition:", err);
        expect(err).to.be.instanceOf(Error);
      }
    });

    it("Adds multiple claims successfully", async () => {
      const claims = [
        { id: "claim-2", url: "https://example.com/claim2.json" },
        { id: "claim-3", url: "https://example.com/claim3.json" },
      ];

      for (const claim of claims) {
        const tx = await program.methods
          .addClaim(testOrgName, claim.id, claim.url, testDataHash)
          .accounts({
            programData: programDataPDA,
            creator: wallet.publicKey,
          })
          .rpc();
        console.log(`Add claim ${claim.id} transaction:`, tx);
      }

      const programData = await program.account.programData.fetch(programDataPDA);
      console.log("Program data after adding multiple claims:", programData);
      const org = programData.organizations.find(o => o.name === testOrgName);
      console.log("Organization claims:", org.claims);
      expect(org.claims).to.have.lengthOf(3);
      expect(org.claims.map(c => c.claimId)).to.include.members(claims.map(c => c.id));
    });

    it("Fails to add claim with empty ID", async () => {
      try {
        await program.methods
          .addClaim(testOrgName, "", testJsonUrl, testDataHash)
          .accounts({
            programData: programDataPDA,
            creator: wallet.publicKey,
          })
          .rpc();
        expect.fail("Should have thrown an error");
      } catch (err) {
        console.log("Expected error on empty claim ID:", err);
        expect(err).to.be.instanceOf(Error);
      }
    });

    it("Fails to add claim with empty URL", async () => {
      try {
        await program.methods
          .addClaim(testOrgName, "claim-4", "", testDataHash)
          .accounts({
            programData: programDataPDA,
            creator: wallet.publicKey,
          })
          .rpc();
        expect.fail("Should have thrown an error");
      } catch (err) {
        console.log("Expected error on empty URL:", err);
        expect(err).to.be.instanceOf(Error);
      }
    });

    it("Fails to add claim with invalid data hash length", async () => {
      const invalidHash = Array.from(new Uint8Array(16)); // Should be 32 bytes
      try {
        await program.methods
          .addClaim(testOrgName, "claim-4", testJsonUrl, invalidHash)
          .accounts({
            programData: programDataPDA,
            creator: wallet.publicKey,
          })
          .rpc();
        expect.fail("Should have thrown an error");
      } catch (err) {
        console.log("Expected error on invalid hash length:", err);
        expect(err).to.be.instanceOf(Error);
      }
    });
  });
});