
#include <zip.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <zlib.h>

#include <openssl/sha.h>
#include <openssl/md5.h>
#include <openssl/evp.h>

int main(int argc, char* argv[]) {
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <zip_file>\n", argv[0]);
        return EXIT_FAILURE;
    }

    FILE* zip_file = fopen(argv[1], "rb");

    if (!zip_file) {
        perror("Failed to open zip file");
        return EXIT_FAILURE;
    }

    fseek(zip_file, 0, SEEK_END);
    uint64_t zip_size = ftell(zip_file);
    fseek(zip_file, 0, SEEK_SET);
    
    if (!zip_file) {
        perror("Failed to open zip file");
        return EXIT_FAILURE;
    }

    int zip_fd = fileno(zip_file);

    void* zip_data = mmap(NULL, zip_size, PROT_READ, MAP_PRIVATE, zip_fd, 0);

    if (zip_data == MAP_FAILED) {
        perror("Failed to map zip file");
        fclose(zip_file);
        return EXIT_FAILURE;
    }

    struct zip_source* source = zip_source_buffer_create(zip_data, zip_size, 0, NULL);
    struct zip* zip = zip_open_from_source(source, ZIP_RDONLY, NULL);

    if (!zip) {
        perror("Failed to open zip from source");
        zip_source_free(source);
        munmap(zip_data, zip_size);
        fclose(zip_file);
        return EXIT_FAILURE;
    }

    zip_int64_t num_entries = zip_get_num_entries(zip, 0);
    printf("Number of entries in zip: %lld\n", num_entries);

    for (zip_int64_t i = 0; i < num_entries; i++) {
        zip_stat_t stat = {0};

        if (zip_stat_index(zip, i, 0, &stat) == 0) {
            printf("Entry %lld: %s (size: %lld)\n", i, stat.name, stat.size);

            unsigned char md5_digest[MD5_DIGEST_LENGTH];
            unsigned char sha1_digest[SHA_DIGEST_LENGTH];

            struct zip_file* file = zip_fopen_index(zip, i, 0);

            if (file) {
                unsigned char* buffer = mmap(NULL, 0x7FFFFFFF, PROT_READ | PROT_WRITE, MAP_ANONYMOUS | MAP_PRIVATE, -1, 0);

                zip_uint64_t bytes_processed = 0;
                unsigned int crc = 0;

                EVP_MD_CTX* md5_ctx = EVP_MD_CTX_new();
                const EVP_MD* md5_type = EVP_md5();
                EVP_DigestInit_ex(md5_ctx, md5_type, NULL);

                EVP_MD_CTX* sha1_ctx = EVP_MD_CTX_new();
                const EVP_MD* sha1_type = EVP_sha1();
                EVP_DigestInit_ex(sha1_ctx, sha1_type, NULL);

                while (bytes_processed < stat.size) {
                    zip_int64_t chunk_size = 0x7FFFFFFF;

                    if (stat.size - bytes_processed < chunk_size) {
                        chunk_size = stat.size - bytes_processed;
                    }

                    zip_int64_t bytes_read = zip_fread(file, buffer, chunk_size);

                    if (bytes_read != chunk_size) {
                        fprintf(stderr, "Failed to read entry %s: expected %lld bytes, got %lld bytes\n", stat.name, chunk_size, bytes_read);
                        break;
                    }

                    crc = crc32(crc, (const unsigned char*)buffer, (uInt)bytes_read);
                    EVP_DigestUpdate(md5_ctx, buffer, bytes_read);
                    EVP_DigestUpdate(sha1_ctx, buffer, bytes_read);

                    bytes_processed += bytes_read;
                }

                if (crc != (unsigned long)stat.crc) {
                    fprintf(stderr, "CRC mismatch for entry %s: expected %08lx, got %08lx\n", stat.name, (unsigned long)stat.crc, crc);
                }

                unsigned char md5_digest[MD5_DIGEST_LENGTH];
                unsigned char sha1_digest[SHA_DIGEST_LENGTH];

                EVP_DigestFinal_ex(md5_ctx, md5_digest, NULL);
                EVP_DigestFinal_ex(sha1_ctx, sha1_digest, NULL);

                EVP_MD_CTX_free(md5_ctx);
                EVP_MD_CTX_free(sha1_ctx);

                printf("MD5: ");
                for (int j = 0; j < MD5_DIGEST_LENGTH; j++) {
                    printf("%02x", md5_digest[j]);
                }
                printf("\n");

                printf("SHA1: ");
                for (int j = 0; j < SHA_DIGEST_LENGTH; j++) {
                    printf("%02x", sha1_digest[j]);
                }
                printf("\n");

                munmap(buffer, 0x7FFFFFFF);
                zip_fclose(file);
            } else {
                perror("Failed to open entry");
            }
        } else {
            perror("Failed to get entry stat");
        }
    }

    zip_close(zip);
    munmap(zip_data, zip_size);
    fclose(zip_file);

    return EXIT_SUCCESS;
}