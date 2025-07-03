// MongoDB initialization script for local development
// Creates database and initial indexes

// Switch to yolo_datasets database
db = db.getSiblingDB('yolo_datasets');

// Create collections with validation
db.createCollection('datasets', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['name', 'status', 'created_at'],
      properties: {
        name: { bsonType: 'string' },
        status: { enum: ['queued', 'processing', 'completed', 'failed'] },
        created_at: { bsonType: 'date' }
      }
    }
  }
});

db.createCollection('import_jobs', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['job_id', 'status', 'created_at'],
      properties: {
        job_id: { bsonType: 'string' },
        status: { enum: ['queued', 'processing', 'completed', 'failed'] },
        created_at: { bsonType: 'date' }
      }
    }
  }
});

db.createCollection('images');

// Create indexes for performance
// Datasets collection
db.datasets.createIndex({ 'status': 1, 'created_at': -1 });
db.datasets.createIndex({ 'created_at': -1 });
db.datasets.createIndex({ 'import_job_id': 1 });

// Import jobs collection  
db.import_jobs.createIndex({ 'job_id': 1 }, { unique: true });
db.import_jobs.createIndex({ 'status': 1, 'created_at': -1 });
db.import_jobs.createIndex({ 'dataset_id': 1 });

// Images collection (critical for 100GB datasets)
db.images.createIndex({ 'dataset_id': 1, 'filename': 1 });
db.images.createIndex({ 'dataset_id': 1, 'annotation_count': 1 });
db.images.createIndex({ 'dataset_id': 1, 'processed_at': -1 });

print('MongoDB initialization completed successfully!');
print('Created collections: datasets, import_jobs, images');
print('Created performance indexes for efficient querying');
