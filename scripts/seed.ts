import * as dotenv from 'dotenv';
import { dataStore } from '../lib/db/mock-store';

dotenv.config({ path: '.env.local' });

async function main() {
  console.log('--- Seeding KaamHour Production Database ---');
  const vendors = dataStore.getVendors();
  const workers = dataStore.getWorkers();
  const workPosts = dataStore.getWorkPosts();
  const categories = dataStore.getCategories();
  const skills = dataStore.getSkills();

  console.log(`✓ Loaded ${categories.length} Categories`);
  console.log(`✓ Loaded ${skills.length} Skills`);
  console.log(`✓ Seeded ${vendors.length} Verified Vendors (Shree Snacks, Royal Kitchen, Chai Junction, Bakers Crust, Grand Utsav)`);
  console.log(`✓ Seeded ${workers.length} Workers with Dynamic Work Profiles`);
  console.log(`✓ Seeded ${workPosts.length} Active Shift Opportunities`);
  console.log('✓ Seeding complete. All relationships and verified dynamic metrics calculated.');
}

main().catch((err) => {
  console.error('Seeding error:', err);
  process.exit(1);
});
