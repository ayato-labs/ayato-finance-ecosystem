// Mock database client for Next.js API routes
export const db = {
  ticket: {
    findUnique: async ({ where }: any) => {
      console.log("Mock findUnique for ID:", where.id);
      return null; // Return null to simulate "not found"
    },
    delete: async ({ where }: any) => {
      console.log("Mock delete for ID:", where.id);
      return { id: where.id };
    }
  }
};
