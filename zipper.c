
#include <zip.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <zlib.h>
#include <string.h>

#include <openssl/sha.h>
#include <openssl/md5.h>
#include <openssl/evp.h>

int main(int argc, char* argv[]) {

    char* stdout_buffer = malloc(0x100000);
    setvbuf(stdout, stdout_buffer, _IOFBF, 0x100000);

    unsigned char* buffer = mmap(NULL, 0x7FFFFFFF, PROT_READ | PROT_WRITE, MAP_ANONYMOUS | MAP_PRIVATE, -1, 0);

    if (buffer == MAP_FAILED) {
        perror("Failed to allocate buffer");
        printf("{\"error\": \"Failed to allocate buffer\"}\n");
        goto done_with_buffer;
    }

    unsigned char sha256_digest[SHA256_DIGEST_LENGTH];
    EVP_MD_CTX* sha256_ctx = EVP_MD_CTX_new();
    const EVP_MD* sha256_type = EVP_sha256();

    unsigned char md5_digest[MD5_DIGEST_LENGTH];
    EVP_MD_CTX* md5_ctx = EVP_MD_CTX_new();
    const EVP_MD* md5_type = EVP_md5();

    unsigned char sha1_digest[SHA_DIGEST_LENGTH];
    EVP_MD_CTX* sha1_ctx = EVP_MD_CTX_new();
    const EVP_MD* sha1_type = EVP_sha1();
    
    while (1) {
        if (feof(stdin)) {
            break;
        }

        char zip_path[512] = {0};
        fgets(zip_path, sizeof(zip_path), stdin);
        int length = strlen(zip_path);

        while (length > 0 && (zip_path[length - 1] == '\n' || zip_path[length - 1] == '\r')) {
            zip_path[--length] = '\0';
        }

        if (zip_path[0] == 0) {
            break;
        }

        FILE* zip_file = fopen(zip_path, "rb");

        printf("{\"path\": \"%s\", ", zip_path);

        if (!zip_file) {
            perror("Failed to open zip file");
            printf("\"error\": \"Failed to open zip file\"}\n");
            goto done;
        }

        fseek(zip_file, 0, SEEK_END);
        uint64_t zip_size = ftell(zip_file);
        fseek(zip_file, 0, SEEK_SET);

        printf("\"size\": %lld, ", zip_size);

        int zip_fd = fileno(zip_file);

        void* zip_data = mmap(NULL, zip_size, PROT_READ, MAP_PRIVATE, zip_fd, 0);

        if (zip_data == MAP_FAILED) {
            perror("Failed to map zip file");
            printf("\"error\": \"Failed to map zip file\"}\n");
            goto done_with_file;
        }

        EVP_DigestInit_ex(sha256_ctx, sha256_type, NULL);
        EVP_DigestUpdate(sha256_ctx, zip_data, zip_size);
        EVP_DigestFinal_ex(sha256_ctx, sha256_digest, NULL);

        struct zip_source* source = zip_source_buffer_create(zip_data, zip_size, 0, NULL);
        struct zip* zip = zip_open_from_source(source, ZIP_RDONLY, NULL);

        if (!zip) {
            perror("Failed to open zip in memory");
            printf("\"error\": \"Failed to open zip in memory\"}\n");
            goto done_with_zip;
        }

        printf("\"sha256\": \"");
        for (int i = 0; i < SHA256_DIGEST_LENGTH; i++) {
            printf("%02x", sha256_digest[i]);
        }

        zip_int64_t num_entries = zip_get_num_entries(zip, 0);
        fprintf(stderr, "Number of entries in zip: %lld\n", num_entries);

        printf("\", \"entries\": [");

        for (zip_int64_t i = 0; i < num_entries; i++) {
            zip_stat_t stat = {0};

            printf("{\"index\": %lld, ", i);

            if (zip_stat_index(zip, i, 0, &stat) == 0) {
                fprintf(stderr, "Entry %lld: %s (size: %lld)\n", i, stat.name, stat.size);

                printf("\"name\": \"%s\", \"size\": %lld, ", stat.name, stat.size);

                struct zip_file* file = zip_fopen_index(zip, i, 0);

                if (file) {
                    zip_uint64_t bytes_processed = 0;
                    unsigned int crc = 0;

                    EVP_DigestInit_ex(md5_ctx, md5_type, NULL);
                    EVP_DigestInit_ex(sha1_ctx, sha1_type, NULL);

                    while (bytes_processed < stat.size) {
                        zip_int64_t chunk_size = 0x7FFFFFFF;

                        if (stat.size - bytes_processed < chunk_size) {
                            chunk_size = stat.size - bytes_processed;
                        }

                        zip_int64_t bytes_read = zip_fread(file, buffer, chunk_size);

                        if (bytes_read != chunk_size) {
                            fprintf(stderr, "Failed to read entry %s: expected %lld bytes, got %lld bytes\n", stat.name, chunk_size, bytes_read);
                            printf("\"error\": \"Failed to read entry\"}]");

                            break;
                        }

                        crc = crc32(crc, (const unsigned char*)buffer, (uInt)bytes_read);
                        //EVP_DigestUpdate(md5_ctx, buffer, bytes_read);
                        EVP_DigestUpdate(sha1_ctx, buffer, bytes_read);

                        bytes_processed += bytes_read;
                    }

                    if (crc != (unsigned long)stat.crc) {
                        fprintf(stderr, "CRC mismatch for entry %s: expected %08lx, got %08lx\n", stat.name, (unsigned long)stat.crc, crc);
                        printf("\"error\": \"CRC mismatch\", \"expected_crc\": \"%08lx\", ", (unsigned long)stat.crc);
                    }

                    printf("\"crc\": \"%08lx\", ", crc);

                    //EVP_DigestFinal_ex(md5_ctx, md5_digest, NULL);
                    EVP_DigestFinal_ex(sha1_ctx, sha1_digest, NULL);

                    /* fprintf(stderr, "MD5: ");
                    printf("\"md5\": \"");
                    for (int j = 0; j < MD5_DIGEST_LENGTH; j++) {
                        fprintf(stderr, "%02x", md5_digest[j]);
                        printf("%02x", md5_digest[j]);
                    }
                    fprintf(stderr, "\n");
                    printf("\", "); */

                    fprintf(stderr, "SHA1: ");
                    printf("\"sha1\": \"");
                    for (int j = 0; j < SHA_DIGEST_LENGTH; j++) {
                        fprintf(stderr, "%02x", sha1_digest[j]);
                        printf("%02x", sha1_digest[j]);
                    }
                    fprintf(stderr, "\n");
                    printf("\"}");

                    zip_fclose(file);
                }
                else {
                    perror("Failed to open entry");
                    printf("\"error\": \"Failed to open entry\"}");
                }
            }
            else {
                perror("Failed to get entry stat");
                printf("\"error\": \"Failed to get entry stat\"}");
            }

            if (i < num_entries - 1) {
                printf(", ");
            }
        }

        printf("]}\n");

    done_with_zip:
        zip_close(zip);
    done_with_buffer:
        munmap(zip_data, zip_size);
    done_with_file:
        fclose(zip_file);
    done:
        fflush(stdout);
    }

    EVP_MD_CTX_free(sha256_ctx);
    EVP_MD_CTX_free(md5_ctx);
    EVP_MD_CTX_free(sha1_ctx);

    munmap(buffer, 0x7FFFFFFF);

    return EXIT_SUCCESS;
}